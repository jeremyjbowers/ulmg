# ABOUTME: What the pitching coach says when a manager has to pull his pitcher.
# ABOUTME: The line is chosen from the game and the pitcher, so a reload says the same thing.

import zlib

# A bench of lines, some straight and some from the movies, for the coach on the mound.
SAYINGS = (
    "He says he's having trouble breathing out of his eyelids.",
    "Don't think, Meat. His arm is doing the thinking, and it says he's done.",
    "There's no crying in baseball. There is a limit, and he just hit it.",
    "If you build it, he will come. This one has come as far as he's going.",
    "He's cooked, skip. The book and the bullpen are on the same page.",
    "I don't like how he's finishing his pitches. Get him out of there.",
    "That was the outing we drew up. Leave him in and you're borrowing an arm.",
    "The stuff is gone. I'm not asking.",
    "He gave you everything he had. Now he gives you the ball.",
    "This is the hook. Don't make me jog out here twice.",
    "His command walked out to the pen. You should follow it.",
    "The radar gun filed a complaint. I'm upholding it.",
    "He's pitching uphill in a parking lot. We're done.",
    "I've seen livelier stuff in a hotel minibar. Bring in the next guy.",
    "His fastball just asked for directions. That's his day.",
    "Skip, the ball looks like it weighs nine pounds. Get someone who's still got six ounces.",
    "The inning is young and his arm is not. I'm not negotiating.",
    "You want him to face another hitter. So does the hitter.",
    "He's got nothing left but a handshake and a souvenir. Call the pen.",
    "Help me help you: take the ball.",
    "Candlesticks make a nice gift. So does a fresh arm.",
    "He's pitching on memory. Memory doesn't miss bats.",
    "We drew this line before the first pitch. He crossed it. The line still counts.",
    "Save him for the next one. This one is over for him.",
)


def saying(game_id, pitcher_id, reason):
    """One line for this moment. The same game, pitcher and reason always get the same line."""
    key = f"{game_id}:{pitcher_id}:{reason}".encode()
    return SAYINGS[zlib.adler32(key) % len(SAYINGS)]
