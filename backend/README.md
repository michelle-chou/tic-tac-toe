# Tic Tac Toe

Tic Tac Toe game with scoreboard. 
React front end, Python (Flask) REST API backend.
The frontend component is located in the frontend folder.

Try it live at: https://obscure-springs-73090.herokuapp.com/
![alt text](https://i.imgur.com/ymupNbC.png "Website")

## Requirements

* Frontend: NodeJS
```
sudo apt install nodejs -y
```

* Backend: Python 3.13 (3.10 or newer works), Flask 3.1

```
sudo apt install python3 python3-venv -y
```

## Running
* Open two terminal windows, in the first run:
```
git clone https://github.com/MiloTodt/tictactoe.git
cd tictactoe/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask db setup
flask run -p 3001
```
On Windows, create and activate the environment with `py -m venv .venv` and `.venv\Scripts\activate`.

`flask db setup` rebuilds the database from `db/schema.py` and loads the five players of `db/seeds.py`;
skip it to keep the scores already stored in `db/development.sqlite3`.

* In the second terminal, navigate to /tictactoe/frontend
```
cd frontend
npm start
```
![alt text](https://i.imgur.com/Y3v6UwB.png "Front")

* This page should open in your browser
![alt text](https://i.imgur.com/ymupNbC.png "Website")

## Layout

| Path | Contents |
| --- | --- |
| `app/controllers` | `PlayersController` (`api/v1` and top level), `GamesController` (`api/v1`) and `ApplicationController` |
| `app/models` | `Player`, `Game` and `ApplicationRecord` |
| `config` | `routes.py`, `database.yml`, the environments and the initializers (CORS, params wrapper) |
| `db` | `schema.py`, `seeds.py`, the migrations and the SQLite databases |
| `lib` | The framework layer the application is written against, on top of Flask and sqlite3 |
| `spec` | The test suite |
| `wsgi.py` | Entry point used by `flask` and by WSGI servers |

## Database tasks

Run from this directory:

```
flask db setup         # create the databases, load db/schema.py, load db/seeds.py
flask db schema:load   # rebuild the tables from db/schema.py (existing rows are dropped)
flask db seed          # load db/seeds.py
flask db migrate       # run the migrations in db/migrate that have not been applied yet
```

The environment is selected with `RAILS_ENV` (`development` by default, `test`, `production`).
A database marked as production is not rebuilt unless `DISABLE_DATABASE_ENVIRONMENT_CHECK=1` is set.

## Tests

```
pytest
```
