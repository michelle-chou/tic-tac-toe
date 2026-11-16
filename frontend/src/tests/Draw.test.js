import React from "react";
import axios from "axios";
import { act, fireEvent, render } from "@testing-library/react";

import { Board } from "../components/Game.js";

jest.mock("axios");

describe("Board: drawn game", () => {
  beforeEach(() => {
    let id = 0;
    jest.clearAllMocks();
    axios.get.mockResolvedValue({ data: [] });
    // answer like the backend: the created player, with its id
    axios.post.mockImplementation((url, body) =>
      Promise.resolve({ data: { id: ++id, ...body.player } })
    );
    // O (player one) moves first
    jest.spyOn(Math, "random").mockReturnValue(0.9);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("Should record a draw for both players", () => {
    const ref = React.createRef();
    const board = render(<Board ref={ref} />);
    act(() => {
      ref.current.setState({ player_one: "Ann", player_two: "Bob" });
    });

    // O X O
    // O X X
    // X O O
    const squares = board.queryAllByTestId("board-square");
    [0, 1, 2, 4, 3, 5, 7, 6, 8].forEach(i => fireEvent.click(squares[i]));

    expect(board.queryByText("The game is a draw!")).not.toBeNull();
    // the two new players, and the game itself
    expect(axios.post).toHaveBeenCalledTimes(3);
    expect(axios.post).toHaveBeenCalledWith("/api/v1/players", {
      player: { name: "Ann", wins: 0, losses: 0, draws: 1 }
    });
    expect(axios.post).toHaveBeenCalledWith("/api/v1/players", {
      player: { name: "Bob", wins: 0, losses: 0, draws: 1 }
    });
    expect(axios.post).toHaveBeenCalledWith("/api/v1/games", {
      game: {
        player_x: "Bob",
        player_o: "Ann",
        winner: null,
        first_player: "O",
        moves: [0, 1, 2, 4, 3, 5, 7, 6, 8]
      }
    });
  });
});
