import React from "react";
import axios from "axios";
import { act, fireEvent, render } from "@testing-library/react";

import { Board } from "../components/Game.js";

jest.mock("axios");

const flush = () => new Promise(resolve => setTimeout(resolve, 0));

describe("Board: saving the finished game for the replays", () => {
  let board, saved, players;

  const renderBoard = async () => {
    const ref = React.createRef();
    board = render(<Board ref={ref} />);
    await act(async () => {
      await flush();
    });
    act(() => {
      ref.current.setState({ player_one: "Ann", player_two: "Bob" });
    });
  };
  const click = (...squares) => {
    const buttons = board.queryAllByTestId("board-square");
    squares.forEach(i => fireEvent.click(buttons[i]));
  };
  // The list of replays is loaded again once the game has been saved:
  // lets the pending requests settle until it shows that many games
  const waitForReplays = async count => {
    const listed = () => board.queryAllByTestId("replay-game").length;
    for (let i = 0; i < 10 && listed() !== count; i++) {
      await act(async () => {
        await flush();
      });
    }
    expect(listed()).toBe(count);
  };
  const gamesPosted = () =>
    axios.post.mock.calls
      .filter(([url]) => url === "/api/v1/games")
      .map(([url, body]) => body.game);

  beforeEach(() => {
    saved = [];
    players = 0;
    jest.clearAllMocks();
    // answer like the backend: games are listed newest first
    axios.get.mockImplementation(url =>
      Promise.resolve({ data: url.startsWith("/api/v1/games") ? saved : [] })
    );
    axios.post.mockImplementation((url, body) => {
      if (url !== "/api/v1/games") {
        return Promise.resolve({ data: { id: ++players, ...body.player } });
      }
      const game = {
        id: saved.length + 1,
        ...body.game,
        created_at: "2026-11-16T12:00:00.000Z"
      };
      saved = [game, ...saved];
      return Promise.resolve({ data: game });
    });
    // X (player two) moves first
    jest.spyOn(Math, "random").mockReturnValue(0.1);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("Should post the squares in the order they were played", async () => {
    await renderBoard();

    // X O X
    // . X O
    // X . O
    click(4, 1, 0, 5, 2, 0, 4, 8);
    click(6, 7);

    expect(board.queryByText("Winner: Bob")).not.toBeNull();
    expect(gamesPosted()).toEqual([
      {
        player_x: "Bob",
        player_o: "Ann",
        winner: "X",
        first_player: "X",
        // without the clicks on taken squares, and the one after the game ended
        moves: [4, 1, 0, 5, 2, 8, 6]
      }
    ]);
  });

  it("Should not post a game before it is finished", async () => {
    await renderBoard();

    click(4, 1, 0, 5);

    expect(gamesPosted()).toEqual([]);
  });

  it("Should not record the clicks made before both players are named", async () => {
    const ref = React.createRef();
    board = render(<Board ref={ref} />);

    click(4, 1);
    act(() => {
      ref.current.setState({ player_one: "Ann", player_two: "Bob" });
    });
    click(0, 3, 1, 4, 2);

    expect(gamesPosted().map(game => game.moves)).toEqual([[0, 3, 1, 4, 2]]);
  });

  it("Should record a new game from its first move", async () => {
    await renderBoard();

    click(0, 3, 1, 4, 2);
    // the first game is left unfinished here
    fireEvent.click(board.getByText("New Game"));
    click(8, 7);
    fireEvent.click(board.getByText("New Game"));
    // O (player one) moves first this time
    Math.random.mockReturnValue(0.9);
    fireEvent.click(board.getByText("New Game"));
    click(6, 0, 4, 1, 2);

    expect(gamesPosted().map(game => game.moves)).toEqual([
      [0, 3, 1, 4, 2],
      [6, 0, 4, 1, 2]
    ]);
    expect(gamesPosted().map(game => game.first_player)).toEqual(["X", "O"]);
    expect(gamesPosted().map(game => game.winner)).toEqual(["X", "O"]);
  });

  it("Should show the saved game in the list of replays", async () => {
    await renderBoard();
    expect(board.queryAllByTestId("replay-game").length).toBe(0);

    click(0, 3, 1, 4, 2);
    await waitForReplays(1);

    const games = board.queryAllByTestId("replay-game");
    expect(games[0].textContent).toContain("Ann (O) vs. Bob (X): Bob won");
    expect(axios.get).toHaveBeenCalledWith("/api/v1/games?limit=10");
  });

  it("Should replay the saved game on its own board", async () => {
    await renderBoard();
    click(0, 3, 1, 4, 2);
    await waitForReplays(1);
    const replayed = () =>
      board.queryAllByTestId("replay-square").map(square => square.textContent);

    jest.useFakeTimers();
    fireEvent.click(board.queryAllByTestId("replay-game")[0]);
    fireEvent.click(board.getByText("Play"));
    expect(replayed()).toEqual(["", "", "", "", "", "", "", "", ""]);
    act(() => {
      jest.advanceTimersByTime(5000);
    });
    jest.useRealTimers();

    expect(replayed()).toEqual(["X", "X", "X", "O", "O", "", "", "", ""]);
    // the board of the game that was played is not touched
    expect(
      board.queryAllByTestId("board-square").map(square => square.textContent)
    ).toEqual(["X", "X", "X", "O", "O", "", "", "", ""]);
  });
});
