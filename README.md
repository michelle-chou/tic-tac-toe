# Tic Tac Toe

Tic Tac Toe game with scoreboard. 
React front end, Python (Flask) REST API backend.

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

## Running With Docker
* Open three terminal windows, in the first run:
```
docker-compose up
```

* In the second terminal, navigate to /tictactoe/frontend
```
docker-compose exec web bash
./entrypoint/backend.sh
```

* In the third terminal, navigate to /tictactoe/frontend
```
docker-compose exec web bash
./entrypoint/frontend.sh
```

## Running Without Docker
* Open two terminal windows, in the first run:
```
git clone https://github.com/MiloTodt/tictactoe.git
cd tictactoe
cd backend
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
