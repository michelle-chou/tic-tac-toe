import React from "react";
import axios from "axios";
import "./Game.css";
import "./Replay.css";

const MOVE_DELAY = 1000; //Milliseconds between two moves of a replay

//Who won a saved game
function gameResult(game) {
  if (game.winner === "X") {
    return game.player_x + " won";
  } else if (game.winner === "O") {
    return game.player_o + " won";
  }
  return "Draw";
}

//The board of a saved game after its first `step` moves
function squaresAt(game, step) {
  const squares = Array(9).fill(null);
  const second = game.first_player === "X" ? "O" : "X";
  game.moves.slice(0, step).forEach((square, turn) => {
    squares[square] = turn % 2 === 0 ? game.first_player : second;
  });
  return squares;
}

class Replay extends React.Component {
  state = {
    games: [],
    selected: null, //The game to replay
    step: 0, //How many of its moves are on the board
    playing: false
  };
  timer = null;
  unmounted = false;

  componentDidMount() {
    this.downloadGames();
  }
  componentWillUnmount() {
    this.unmounted = true;
    this.stopTimer();
  }
  //Loads the most recent games. Also called by the board when a game has been saved.
  downloadGames() {
    axios
      .get("/api/v1/games?limit=10")
      .then(response => {
        if (!this.unmounted) {
          this.setState({ games: response.data });
        }
      })
      .catch(error => console.log(error));
  }
  stopTimer() {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
  //Selecting another game ends the replay that is running
  selectGame(game) {
    if (this.state.selected && this.state.selected.id === game.id) {
      return;
    }
    this.stopTimer();
    this.setState({ selected: game, step: 0, playing: false });
  }
  //Starts from an empty board, then shows one more move every second
  play() {
    const game = this.state.selected;
    if (!game) {
      return;
    }
    this.stopTimer(); //Pressing Play during a replay starts it over
    let step = 0;
    this.setState({ step: step, playing: true });
    this.timer = setInterval(() => {
      step++;
      const finished = step >= game.moves.length;
      if (finished) {
        this.stopTimer();
      }
      this.setState({ step: step, playing: !finished });
    }, MOVE_DELAY);
  }

  renderSquare(squares, i) {
    return (
      <div className="square replay-square" data-testid="replay-square">
        {squares[i]}
      </div>
    );
  }

  render() {
    const { games, selected, step, playing } = this.state;
    const squares = selected ? squaresAt(selected, step) : Array(9).fill(null);

    let status;
    if (!selected) {
      status = games.length > 0 ? "Select a game to replay." : "No games played yet.";
    } else if (playing) {
      status = "Move " + step + " of " + selected.moves.length;
    } else if (step > 0) {
      status = "Replay finished: " + gameResult(selected);
    } else {
      status = "Press Play to watch the game.";
    }

    return (
      <>
        <h4 align="left">Replay</h4>
        <div className="card-replay" data-testid="game-replay">
          <div className="list-group replay-games">
            {games.map(game => (
              <button
                type="button"
                key={game.id}
                className={
                  "list-group-item list-group-item-action" +
                  (selected && selected.id === game.id ? " active" : "")
                }
                aria-pressed={selected !== null && selected.id === game.id}
                onClick={() => this.selectGame(game)}
                data-testid="replay-game"
              >
                {game.player_o} (O) vs. {game.player_x} (X): {gameResult(game)}
                <span className="replay-date">
                  {new Date(game.created_at).toLocaleString()}
                </span>
              </button>
            ))}
          </div>
          <div className="status" data-testid="replay-status">
            {status}
          </div>
          <div className="card-game" data-testid="replay-board">
            <div className="board-row">
              <div className="col-sm-12 col-md-6 offset-md-3">
                {this.renderSquare(squares, 0)} {this.renderSquare(squares, 1)}
                {this.renderSquare(squares, 2)}
              </div>
            </div>
            <div className="board-row">
              <div className="col-sm-12 col-md-6 offset-md-3">
                {this.renderSquare(squares, 3)} {this.renderSquare(squares, 4)}
                {this.renderSquare(squares, 5)}
              </div>
            </div>
            <div className="board-row">
              <div className="col-sm-12 col-md-6 offset-md-3">
                {this.renderSquare(squares, 6)} {this.renderSquare(squares, 7)}
                {this.renderSquare(squares, 8)}
              </div>
            </div>
          </div>
          <button
            className="btn btn-primary"
            disabled={!selected}
            onClick={() => this.play()}
          >
            Play
          </button>
        </div>
      </>
    );
  }
}

export default Replay;
