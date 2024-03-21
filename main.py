from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import json
import random
import time
from flask_cors import CORS

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')
CORS(app)

game_started = False

with open('templates/words.json') as f:
    word_list = json.load(f)

def get_random_word():
    word = random.choice(word_list)
    return word['word_entry'], word['description']

players = []
current_word = ""
current_word_revealed = []
turn_time = 10

@app.route('/')
def index():
    return render_template('index.html', players=players)

@socketio.on('connect')
def on_connect():
    player_id = request.sid
    players.append({'player_id': player_id, 'name': '', 'score': 0, 'is_ready': False})

@socketio.on('disconnect')
def on_disconnect():
    player_id = request.sid
    players[:] = [player for player in players if player['player_id'] != player_id]
    emit('player_list', {'players': [p for p in players if p['name'] != ""]}, broadcast=True)
    if len(players) == 0 or len([p for p in players if p['name'] != ""]) == 0:
        end_game()


@socketio.on('player_name')
def set_player_name(data):
    player_id = request.sid
    player = next((p for p in players if p['player_id'] == player_id), None)
    if player:
        player['name'] = data['name']
        emit('message', {'message': f'Hi {data["name"]}! Please click "Ready" to start the game.'})
        emit('player_list', {'players': [p for p in players if p['name'] != ""]}, broadcast=True)

@socketio.on('ready')
def on_ready():
    global game_started
    player_id = request.sid
    player = next((p for p in players if p['player_id'] == player_id and p['name'] != ""), None)
    if player:
        player['is_ready'] = True
        emit('player_list', {'players': [p for p in players if p['name'] != ""]}, broadcast=True)

    all_ready = all(player['is_ready'] for player in players if player['name'] != "")

    if all_ready and not game_started:
        game_started = True
        start_game()

@socketio.on('guess')
def on_guess(data):
    player_id = request.sid
    player = next((p for p in players if p['player_id'] == player_id), None)
    if player and player['is_ready']:
        if player.get('guess') is None:
            guess = data.get('guess')
            if guess and len(guess) == 1:
                player['guess'] = guess.lower()

def start_game():
    global current_word, current_word_revealed, game_started
    current_word, description = get_random_word()
    current_word_revealed = ['-' if c != ' ' else ' ' for c in current_word]

    emit('message', {'message': 'Game starts now!'}, broadcast=True)
    emit('word', {'revealed_word': current_word_revealed, 'description': description}, broadcast=True)
    emit('hint', {'hint': ''.join(current_word_revealed)}, broadcast=True)
    for player in players:
        player['score'] = 0
    emit('player_list', {'players': [p for p in players if p['name'] != ""]}, broadcast=True)
    while '-' in current_word_revealed:
        for sec in range(turn_time, 0, -1):
            if sec == 10:
                emit('again', {'message': 'again'}, broadcast=True)
            if len(players) == 0 or len([p for p in players if p['name'] != ""]) == 0:
                break
            emit('countdown', {'time': sec}, broadcast=True)

            time.sleep(1)
            for player in players:
                if player.get('guess'):
                    guess = player['guess'].lower()
                    if guess in current_word_revealed or guess.upper() in current_word_revealed:
                        emit('message', {'message': 'Wrong guess!'},
                             room=player['player_id'])
                        player['guess'] = None
                    elif guess in current_word.lower():
                        for i, char in enumerate(current_word):
                            if char.lower() == guess:
                                current_word_revealed[i] = char if char != ' ' else ' '
                        emit('reveal', {'revealed_word': current_word_revealed}, broadcast=True)

                        score = current_word.lower().count(guess) * 100
                        player['score'] += score
                        player['guess'] = None
                        emit('player_list', {'players': [p for p in players if p['name'] != ""]}, broadcast=True)
                        emit('message', {'message': 'Right guess!'},
                             room=player['player_id'])
                    else:
                        emit('player_list', {'players': [p for p in players if p['name'] != ""]}, broadcast=True)
                        emit('message', {'message': 'Wrong guess!'},
                             room=player['player_id'])
                        player['guess'] = None

        emit('reveal', {'revealed_word': current_word_revealed}, broadcast=True)

    end_game()


def end_game():
    global game_started
    game_started = False
    players_with_name = [p for p in players if p['name'] != ""]


    if len(players_with_name) > 0:
        total_scores = {player['player_id']: player['score'] for player in players_with_name}
        winner_id = max(total_scores, key=total_scores.get)
        max_score = total_scores[winner_id]
        emit('player_list', {'players': players_with_name}, broadcast=True)
        for player in players_with_name:
            emit('end_game', {'message': 'end_game'}, broadcast=True)
            player['is_ready'] = False
            score = player['score']
            if player['score'] == max_score:
                emit('message', {'message': f'You win with total score of {max_score}!'}, room=player['player_id'])
            else:
                emit('message', {'message': f'You lose with total score of {score}!'}, room=player['player_id'])
            
    emit('player_list', {'players': [p for p in players if p['name'] != ""]}, broadcast=True)
    global current_word
    current_word = ""
    global current_word_revealed
    current_word_revealed = []

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
