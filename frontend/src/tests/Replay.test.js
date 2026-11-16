import React from "react";
import axios from "axios";
import { act, cleanup, fireEvent, render } from "@testing-library/react";

import Replay from "../components/Replay.js";

jest.mock("axios");

const flush = () => new Promise(resolve => setTimeout(resolve, 0));

// The newest game comes first, as the backend lists them.
const draw = {
  // O X O
  // O X X
  // X O O
  id: 2,
  player_x: "Bob",
  player_o: "Ann",
  winner: null,
  first_player: "O",
  moves: [0, 1, 2, 4, 3, 5, 7, 6, 8],
  created_at: "2026-11-16T12:05:00.000Z"
};
const win = {
  // X X X
  // O O .
  // . . .
  id: 1,
  player_x: "Bob",
  player_o: "Ann",
  winner: "X",
  first_player: "X",
  moves: [0, 3, 1, 4, 2],
  created_at: "2026-11-16T12:00:00.000Z"
};
const EMPTY = ["", "", "", "", "", "", "", "", ""];

describe("Replay", () => {
  let ref, replay;

  // Renders the component, waits for its list of games, then takes over the clock
  const renderReplay = async () => {
    ref = React.createRef();
    replay = render(<Replay ref={ref} />);
    await act(async () => {
      await flush();
    });
    jest.useFakeTimers();
  };
  const select = game => {
    const index = [draw, win].indexOf(game);
    fireEvent.click(replay.queryAllByTestId("replay-game")[index]);
  };
  const play = () => fireEvent.click(replay.getByText("Play"));
  const wait = milliseconds =>
    act(() => {
      jest.advanceTimersByTime(milliseconds);
    });
  const board = () =>
    replay.queryAllByTestId("replay-square").map(square => square.textContent);
  const status = () => replay.getByTestId("replay-status").textContent;

  beforeEach(() => {
    jest.clearAllMocks();
    axios.get.mockImplementation(() =>
      // new objects for every request, like a response of the backend
      Promise.resolve({ data: [{ ...draw }, { ...win }] })
    );
  });

  afterEach(() => {
    // unmount while the fake clock is still there, for a replay that is
    // still running to clear its timer on it
    cleanup();
    jest.useRealTimers();
  });

  it("Should list the ten most recent games", async () => {
    await renderReplay();

    const games = replay.queryAllByTestId("replay-game");
    expect(axios.get).toHaveBeenCalledTimes(1);
    expect(axios.get).toHaveBeenCalledWith("/api/v1/games?limit=10");
    expect(games.length).toBe(2);
    expect(games[0].textContent).toContain("Ann (O) vs. Bob (X): Draw");
    expect(games[1].textContent).toContain("Ann (O) vs. Bob (X): Bob won");
    expect(status()).toBe("Select a game to replay.");
  });

  it("Should render without any game", async () => {
    axios.get.mockResolvedValue({ data: [] });
    await renderReplay();

    expect(replay.queryAllByTestId("replay-game").length).toBe(0);
    expect(status()).toBe("No games played yet.");
    expect(board()).toEqual(EMPTY);
    expect(replay.getByText("Play").disabled).toBe(true);
  });

  it("Should render when the games cannot be loaded", async () => {
    jest.spyOn(console, "log").mockImplementation(() => {});
    axios.get.mockRejectedValue(new Error("Network Error"));
    await renderReplay();

    expect(replay.queryByTestId("game-replay")).not.toBeNull();
    expect(replay.queryAllByTestId("replay-game").length).toBe(0);
    console.log.mockRestore();
  });

  it("Should play only once a game is selected", async () => {
    await renderReplay();

    expect(replay.getByText("Play").disabled).toBe(true);
    play();
    expect(setInterval).not.toHaveBeenCalled();

    select(win);
    expect(replay.getByText("Play").disabled).toBe(false);
    expect(replay.queryAllByTestId("replay-game")[1].className).toContain("active");
    expect(replay.queryAllByTestId("replay-game")[0].className).not.toContain("active");
    expect(status()).toBe("Press Play to watch the game.");
    expect(board()).toEqual(EMPTY);
    expect(setInterval).not.toHaveBeenCalled();
  });

  it("Should show the moves one per second on an empty board", async () => {
    await renderReplay();
    select(win);
    play();

    expect(setInterval).toHaveBeenCalledTimes(1);
    expect(setInterval).toHaveBeenLastCalledWith(expect.any(Function), 1000);
    expect(board()).toEqual(EMPTY);
    expect(status()).toBe("Move 0 of 5");

    wait(999);
    expect(board()).toEqual(EMPTY);
    wait(1);
    expect(board()).toEqual(["X", "", "", "", "", "", "", "", ""]);
    expect(status()).toBe("Move 1 of 5");
    wait(1000);
    expect(board()).toEqual(["X", "", "", "O", "", "", "", "", ""]);
    wait(1000);
    expect(board()).toEqual(["X", "X", "", "O", "", "", "", "", ""]);
    wait(1000);
    expect(board()).toEqual(["X", "X", "", "O", "O", "", "", "", ""]);
    expect(status()).toBe("Move 4 of 5");
    wait(1000);
    expect(board()).toEqual(["X", "X", "X", "O", "O", "", "", "", ""]);
    expect(status()).toBe("Replay finished: Bob won");
  });

  it("Should give the first move to the player who started the game", async () => {
    await renderReplay();
    select(draw);
    play();

    wait(1000);
    expect(board()).toEqual(["O", "", "", "", "", "", "", "", ""]);
    wait(8000);
    expect(board()).toEqual(["O", "X", "O", "O", "X", "X", "X", "O", "O"]);
    expect(status()).toBe("Replay finished: Draw");
  });

  it("Should stop the timer when the replay finishes", async () => {
    await renderReplay();
    select(win);
    play();
    const timer = ref.current.timer;

    wait(4000);
    expect(timer).not.toBeNull();
    expect(clearInterval).not.toHaveBeenCalled();
    wait(1000);
    expect(clearInterval).toHaveBeenCalledTimes(1);
    expect(clearInterval).toHaveBeenCalledWith(timer);
    expect(ref.current.timer).toBeNull();

    wait(10000);
    expect(board()).toEqual(["X", "X", "X", "O", "O", "", "", "", ""]);
    expect(status()).toBe("Replay finished: Bob won");
    expect(clearInterval).toHaveBeenCalledTimes(1);
  });

  it("Should stop the timer when a different game is selected", async () => {
    await renderReplay();
    select(win);
    play();
    const timer = ref.current.timer;
    wait(2000);
    expect(board()).toEqual(["X", "", "", "O", "", "", "", "", ""]);

    select(draw);
    expect(clearInterval).toHaveBeenCalledTimes(1);
    expect(clearInterval).toHaveBeenCalledWith(timer);
    expect(ref.current.timer).toBeNull();
    expect(board()).toEqual(EMPTY);
    expect(status()).toBe("Press Play to watch the game.");

    // nothing moves until Play is pressed for the newly selected game
    wait(10000);
    expect(board()).toEqual(EMPTY);
    expect(status()).toBe("Press Play to watch the game.");

    play();
    wait(1000);
    expect(board()).toEqual(["O", "", "", "", "", "", "", "", ""]);
  });

  it("Should go on when the game being replayed is selected again", async () => {
    await renderReplay();
    select(win);
    play();
    wait(1000);

    select(win);
    expect(clearInterval).not.toHaveBeenCalled();
    wait(1000);
    expect(board()).toEqual(["X", "", "", "O", "", "", "", "", ""]);
  });

  it("Should start over, with a single timer, when Play is pressed again", async () => {
    await renderReplay();
    select(win);
    play();
    const timer = ref.current.timer;
    wait(2500);
    expect(board()).toEqual(["X", "", "", "O", "", "", "", "", ""]);

    play();
    expect(clearInterval).toHaveBeenCalledWith(timer);
    expect(board()).toEqual(EMPTY);
    wait(999);
    expect(board()).toEqual(EMPTY);
    wait(1);
    expect(board()).toEqual(["X", "", "", "", "", "", "", "", ""]);
    wait(4000);
    expect(board()).toEqual(["X", "X", "X", "O", "O", "", "", "", ""]);
    expect(setInterval).toHaveBeenCalledTimes(2);
    expect(clearInterval).toHaveBeenCalledTimes(2);
  });

  it("Should replay a finished replay from an empty board", async () => {
    await renderReplay();
    select(win);
    play();
    wait(5000);
    expect(status()).toBe("Replay finished: Bob won");

    play();
    expect(board()).toEqual(EMPTY);
    wait(5000);
    expect(board()).toEqual(["X", "X", "X", "O", "O", "", "", "", ""]);
    expect(ref.current.timer).toBeNull();
  });

  it("Should go on when the list of games is loaded again", async () => {
    await renderReplay();
    select(win);
    play();
    wait(1000);

    // a game that has just been saved comes first in the list
    const newest = { ...draw, id: 3 };
    axios.get.mockResolvedValue({ data: [newest, { ...draw }, { ...win }] });
    await act(async () => {
      ref.current.downloadGames();
      for (let i = 0; i < 5; i++) {
        await Promise.resolve();
      }
    });

    const games = replay.queryAllByTestId("replay-game");
    expect(games.length).toBe(3);
    expect(games[2].className).toContain("active");
    expect(clearInterval).not.toHaveBeenCalled();
    wait(1000);
    expect(board()).toEqual(["X", "", "", "O", "", "", "", "", ""]);
  });

  it("Should stop the timer when it is removed from the page", async () => {
    const error = jest.spyOn(console, "error").mockImplementation(() => {});
    await renderReplay();
    select(win);
    play();
    const timer = ref.current.timer;
    wait(1000);

    replay.unmount();
    expect(clearInterval).toHaveBeenCalledWith(timer);
    wait(10000);
    expect(error).not.toHaveBeenCalled();
    error.mockRestore();
  });
});
