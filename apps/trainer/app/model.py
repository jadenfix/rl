"""Dependency-free Bradley–Terry reward baseline; does not train a language model."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

FEATURES = ("prompt_overlap", "word_count", "unique_fraction", "question", "exclamation")
FORMAT = "rlaas-linear-preference-v1"
MAX_TEXT = 2000


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise ValueError("text must be a nonempty string of at most 2000 characters")
    return value


def features(prompt, response):
    prompt_words = set(text(prompt).lower().split())
    words = text(response).lower().split()
    unique = set(words)
    return [len(prompt_words & unique) / len(prompt_words),
            min(len(words), 200) / 200, len(unique) / len(words),
            float("?" in response), float("!" in response)]


def validate_pairs(data):
    if not isinstance(data, list) or not 2 <= len(data) <= 256:
        raise ValueError("pairs must contain between 2 and 256 preferences")
    result = []
    for pair in data:
        if not isinstance(pair, dict) or set(pair) != {"prompt", "chosen", "rejected"}:
            raise ValueError("each pair must contain only prompt, chosen and rejected")
        chosen = features(pair["prompt"], pair["chosen"])
        rejected = features(pair["prompt"], pair["rejected"])
        delta = [a-b for a, b in zip(chosen, rejected)]
        if not any(delta):
            raise ValueError("chosen and rejected must have distinguishable features")
        result.append(delta)
    return result


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def loss(weights, deltas):
    # Stable softplus(-margin).
    values = [-dot(weights, delta) for delta in deltas]
    return sum(max(v, 0) + math.log1p(math.exp(-abs(v))) for v in values) / len(values)


def train(pairs, epochs=200, learning_rate=0.5):
    data = pairs
    deltas = validate_pairs(data)
    if type(epochs) is not int or not 1 <= epochs <= 2000:
        raise ValueError("epochs must be an integer between 1 and 2000")
    if type(learning_rate) not in (int, float) or not math.isfinite(learning_rate) or not 0 < learning_rate <= 2:
        raise ValueError("learning_rate must be finite and in (0, 2]")
    weights = [0.0] * len(FEATURES)
    initial = loss(weights, deltas)
    for _ in range(epochs):
        gradient = [0.0] * len(weights)
        for delta in deltas:
            margin = dot(weights, delta)
            probability = (math.exp(-margin)/(1+math.exp(-margin)) if margin >= 0
                           else 1/(1+math.exp(margin)))
            for i, value in enumerate(delta):
                gradient[i] -= probability * value / len(deltas)
        weights = [w-learning_rate*g for w, g in zip(weights, gradient)]
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return {"format": FORMAT, "features": list(FEATURES), "weights": weights,
            "training": {"pairs": len(data), "epochs": epochs, "learning_rate": learning_rate,
                         "initial_loss": initial, "final_loss": loss(weights, deltas),
                         "training_preference_accuracy": sum(dot(weights, d) > 0 for d in deltas)/len(deltas),
                         "dataset_sha256": hashlib.sha256(canonical).hexdigest()}}


def validate_model(model):
    if not isinstance(model, dict) or set(model) != {"format", "features", "weights", "training"}:
        raise ValueError("invalid checkpoint fields")
    if model["format"] != FORMAT or model["features"] != list(FEATURES):
        raise ValueError("unsupported checkpoint format or feature schema")
    weights = model["weights"]
    if not isinstance(weights, list) or len(weights) != len(FEATURES) or any(
            type(w) not in (int, float) or not math.isfinite(w) or abs(w) > 10000 for w in weights):
        raise ValueError("invalid checkpoint weights")
    receipt = model["training"]
    expected = {"pairs", "epochs", "learning_rate", "initial_loss", "final_loss",
                "training_preference_accuracy", "dataset_sha256"}
    if not isinstance(receipt, dict) or set(receipt) != expected:
        raise ValueError("invalid checkpoint training receipt")
    digest = receipt["dataset_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("invalid checkpoint dataset digest")
    for key in expected - {"dataset_sha256"}:
        value = receipt[key]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("invalid checkpoint measurement")
    return model


def load(path):
    checkpoint = Path(path)
    if checkpoint.stat().st_size > 65536:
        raise ValueError("checkpoint exceeds 65536 bytes")
    return validate_model(json.loads(checkpoint.read_text()))


def save(path, model):
    validate_model(model)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(model, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        # Persist the rename as well as the file contents on POSIX.
        directory = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def score(model, prompt, response):
    validate_model(model)
    vector = features(prompt, response)
    return {"reward": dot(model["weights"], vector), "features": dict(zip(FEATURES, vector)),
            "model": FORMAT, "dataset_sha256": model["training"]["dataset_sha256"]}
