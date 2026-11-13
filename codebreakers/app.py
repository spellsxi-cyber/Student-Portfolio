import os
import random
import string

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "codebreakers-secret-key")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

rooms = {}


def generate_room_code():
    while True:
        code = ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        if code not in rooms:
            return code


@app.route("/")
def home():
    return render_template("index.html")


def send_error(message):
    emit("error_message", {"message": message}, to=request.sid)


@socketio.on("create_room")
def create_room():
    room_code = generate_room_code()

    rooms[room_code] = {
        "players": [request.sid],
        "secret_codes": {},
        "current_turn": 0,
        "game_over": False
    }

    join_room(room_code)

    emit("room_created", {"room_code": room_code}, to=request.sid)


@socketio.on("join_room")
def handle_join_room(data):
    room_code = str(data.get("room_code", "")).strip().upper()

    if not room_code or room_code not in rooms:
        send_error("Room not found.")
        return

    room = rooms[room_code]

    if request.sid in room["players"]:
        send_error("You are already in this room.")
        return

    if len(room["players"]) >= 2:
        send_error("Room is full.")
        return

    if room["game_over"]:
        send_error("This game has already ended.")
        return

    join_room(room_code)
    room["players"].append(request.sid)

    emit("room_joined", {"room_code": room_code}, to=request.sid)

    emit(
        "player_joined",
        {"message": "Your opponent has joined!"},
        to=room["players"][0]
    )


@socketio.on("submit_secret")
def handle_secret(data):
    room_code = str(data.get("room_code", "")).strip().upper()
    secret_code = str(data.get("secret_code", ""))

    if room_code not in rooms:
        send_error("Room not found.")
        return

    room = rooms[room_code]

    if request.sid not in room["players"]:
        send_error("You are not in this room.")
        return

    if len(room["players"]) != 2:
        send_error("Waiting for the second player.")
        return

    if request.sid in room["secret_codes"]:
        send_error("You have already submitted your secret code.")
        return

    if (
        len(secret_code) != 4
        or not secret_code.isdigit()
        or len(set(secret_code)) != 4
    ):
        send_error("Your secret code must contain four different digits.")
        return

    room["secret_codes"][request.sid] = secret_code

    emit(
        "secret_received",
        {"message": "Your secret code has been saved."},
        to=request.sid
    )

    if len(room["secret_codes"]) == 2:
        first_player = room["players"][0]

        emit(
            "game_ready",
            {"message": "Both players are ready!"},
            to=room_code
        )

        emit(
            "turn_changed",
            {"current_player": first_player},
            to=room_code
        )


@socketio.on("submit_guess")
def handle_guess(data):
    room_code = str(data.get("room_code", "")).strip().upper()
    guess = str(data.get("guess", ""))

    if room_code not in rooms:
        send_error("Room not found.")
        return

    room = rooms[room_code]
    player = request.sid

    if player not in room["players"]:
        send_error("You are not in this room.")
        return

    if len(room["secret_codes"]) != 2:
        send_error("Both players must submit their secret codes.")
        return

    if room["game_over"]:
        send_error("This game has ended.")
        return

    if room["players"][room["current_turn"]] != player:
        send_error("It is not your turn.")
        return

    if (
        len(guess) != 4
        or not guess.isdigit()
        or len(set(guess)) != 4
    ):
        send_error("Enter four different digits from 0 to 9.")
        return

    opponent = next(
        p for p in room["players"] if p != player
    )

    secret = room["secret_codes"][opponent]

    locked_in = sum(
        guess[i] == secret[i] for i in range(4)
    )

    misplaced = sum(
        digit in secret for digit in guess
    ) - locked_in

    winner = locked_in == 4

    emit(
        "guess_result",
        {
            "guess": guess,
            "locked_in": locked_in,
            "misplaced": misplaced,
            "winner": winner
        },
        to=player
    )

    if winner:
        room["game_over"] = True

        emit(
            "opponent_won",
            {"message": "Your opponent cracked your code!"},
            to=opponent
        )

        emit(
            "turn_changed",
            {"current_player": None},
            to=room_code
        )

        return

    emit(
        "opponent_guessed",
        {"message": "Your opponent has made a guess."},
        to=opponent
    )

    room["current_turn"] = 1 - room["current_turn"]

    next_player = room["players"][room["current_turn"]]

    emit(
        "turn_changed",
        {"current_player": next_player},
        to=room_code
    )


@socketio.on("disconnect")
def handle_disconnect():
    player = request.sid

    for room_code, room in list(rooms.items()):
        if player in room["players"]:
            opponent = next(
                (p for p in room["players"] if p != player),
                None
            )

            if opponent:
                emit(
                    "error_message",
                    {"message": "Your opponent disconnected. The room has ended."},
                    to=opponent
                )

            del rooms[room_code]
            break


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False
    )