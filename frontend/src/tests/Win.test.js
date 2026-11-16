import React from "react";
import axios from "axios";
import { act, fireEvent, render } from "@testing-library/react";

import { Board } from "../components/Game.js";

jest.mock("axios");

const flush = () => new Promise(resolve => setTimeout(resolve, 0));

describe("Board: game won between two players already on the scoreboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // the scoreboard loads the players, the replay list loads the games
    axios.get.mockImplementation(url =>
      Promise.resolve({
        data: url.startsWith("/api/v1/games")
          ? []
          : [
              { id: 1, name: "Ann", wins: 2, losses: 1, draws: 0 },
              { id: 2, name: "Bob", wins: 1, losses: 2, draws: 0 }
            ]
      })
    );
    axios.put.mockResolvedValue({ data: null });
    axios.post.mockResolvedValue({ data: { id: 3 } });
    // O (player one) moves first
    jest.spyOn(Math, "random").mockReturnValue(0.9);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("Should save and show the result of both players", async () => {
    const ref = React.createRef();
    const board = render(<Board ref={ref} />);
    await act(async () => {
      await flush();
    });
    act(() => {
      ref.current.setState({ player_one: "Ann", player_two: "Bob" });
    });

    // O O O
    // X X .
    // . . .
    const squares = board.queryAllByTestId("board-square");
    [0, 3, 1, 4, 2].forEach(i => fireEvent.click(squares[i]));
    await act(async () => {
      await flush();
    });

    expect(board.queryByText("Winner: Ann")).not.toBeNull();
    expect(axios.put).toHaveBeenCalledTimes(2);
    expect(axios.put).toHaveBeenCalledWith("/api/v1/players/1", {
      player: { wins: 3, losses: 1, draws: 0 }
    });
    expect(axios.put).toHaveBeenCalledWith("/api/v1/players/2", {
      player: { wins: 1, losses: 3, draws: 0 }
    });
    expect(ref.current.scoreboard.current.state.players).toEqual([
      { id: 1, name: "Ann", wins: 3, losses: 1, draws: 0 },
      { id: 2, name: "Bob", wins: 1, losses: 3, draws: 0 }
    ]);
  });

  it("Should count a finished game only once", async () => {
    const submitNames = (player_one, player_two) =>
      act(() => {
        ref.current.handleSubmit({
          target: { player_one: { value: player_one }, player_two: { value: player_two } },
          preventDefault: () => {}
        });
      });
    const ref = React.createRef();
    const board = render(<Board ref={ref} />);
    await act(async () => {
      await flush();
    });
    submitNames("Ann", "Bob");

    const squares = board.queryAllByTestId("board-square");
    [0, 3, 1, 4, 2].forEach(i => fireEvent.click(squares[i]));
    await act(async () => {
      await flush();
    });
    expect(axios.put).toHaveBeenCalledTimes(2);

    // The finished board is still showing: submitting the names form again,
    // with the same or with other names, must not save the game again.
    submitNames("Ann", "Bob");
    submitNames("Ann", "Bob");
    submitNames("Ann", "Cy");
    fireEvent.click(squares[8]);
    await act(async () => {
      await flush();
    });

    expect(axios.put).toHaveBeenCalledTimes(2);
    // no new player, and the game is saved for the replays once
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post).toHaveBeenCalledWith("/api/v1/games", {
      game: {
        player_x: "Bob",
        player_o: "Ann",
        winner: "O",
        first_player: "O",
        moves: [0, 3, 1, 4, 2]
      }
    });
  });
});
