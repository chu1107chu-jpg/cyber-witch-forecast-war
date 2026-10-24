"""
Боевой движок Political Arena.
3 раунда, выбор хода каждый раунд, house edge 70/30.

Логика:
1. Игрок выбирает 2 бойцов → ставка на одного
2. Движок «объективно» решает кто сильнее (stat+matchup)
3. Симуляция 3 раундов с ходами AI
4. House edge: 70% — побеждает фаворит, 30% — андердог
5. Результат + нарратив для фронтенда
"""

from __future__ import annotations

import hashlib
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any

from game.fighters import FIGHTERS

# ── Константы ────────────────────────────────────────────
ROUNDS = 3
HOUSE_EDGE = 0.70          # 70% времени побеждает объективно сильнейший
CRIT_CHANCE = 0.12          # 12% базовый крит
CRIT_MULT = 1.6             # x1.6 урон крита
MIN_DAMAGE = 1              # минимальный урон
MAX_BET = 100               # макс ставка в ₲
MIN_BET = 1                 # мин ставка в ₲
PAYOUT_MULT = 2.0           # x2 выплата при выигрыше
FREE_FIGHTS_PER_DAY = 3



# ── Модели данных ────────────────────────────────────────

@dataclass
class RoundResult:
    round_num: int
    fighter_a_move: dict
    fighter_b_move: dict
    damage_to_a: int
    damage_to_b: int
    hp_a_after: int
    hp_b_after: int
    crit_a: bool = False
    crit_b: bool = False
    effect_a: str = ""
    effect_b: str = ""
    narration: str = ""


@dataclass
class FightResult:
    fight_id: str
    fighter_a: dict
    fighter_b: dict
    rounds: list[RoundResult] = field(default_factory=list)
    winner_id: str = ""
    objective_winner_id: str = ""
    is_upset: bool = False
    narration: str = ""
    bet_fighter_id: str = ""
    bet_amount: int = 0
    payout: int = 0
    bet_won: bool = False
    server_seed: str = ""
    client_seed: str = ""
    nonce: int = 0


# ── Утилиты ──────────────────────────────────────────────

def _get_fighter(fid: str) -> dict | None:
    for f in FIGHTERS:
        if f["id"] == fid:
            return f
    return None


def _fighter_index() -> dict[str, dict]:
    return {f["id"]: f for f in FIGHTERS}


def _generate_fight_id() -> str:
    return hashlib.sha256(f"{time.time()}{random.random()}".encode()).hexdigest()[:16]


def _provably_fair_seed(server_seed: str, client_seed: str, nonce: int) -> float:
    """Provably fair: SHA256(server+client+nonce) → float 0..1."""
    combined = f"{server_seed}:{client_seed}:{nonce}"
    h = hashlib.sha256(combined.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF





# ── Объективный анализ «кто сильнее» ─────────────────────

def _compute_power_score(fighter: dict, opponent: dict) -> float:
    """Сводный рейтинг силы бойца с учётом матчапа."""
    base = (
        fighter["hp"] * 0.3 +
        fighter["atk"] * 2.5 +
        fighter["def"] * 1.5 +
        fighter["spd"] * 1.2 +
        fighter["luck"] * 0.8
    )
    return base


def compute_objective_winner(fa: dict, fb: dict) -> tuple[str, float]:
    """Возвращает (id_победителя, вероятность_победы 0.5..0.95)."""
    pa = _compute_power_score(fa, fb)
    pb = _compute_power_score(fb, fa)
    total = pa + pb
    if total == 0:
        return fa["id"], 0.5
    prob_a = pa / total
    # Ограничиваем: не меньше 0.30, не больше 0.70 (всегда есть шанс)
    prob_a = max(0.30, min(0.70, prob_a))
    if prob_a >= 0.5:
        return fa["id"], prob_a
    return fb["id"], 1.0 - prob_a


# ── AI для выбора хода ───────────────────────────────────

def _ai_pick_move(fighter: dict, round_num: int,
                  own_hp: int, enemy_hp: int,
                  rng: random.Random) -> dict:
    """Простой AI: выбирает ход в зависимости от HP и раунда."""
    moves = fighter["moves"]
    available = []
    for m in moves:
        if m["type"] == "ultimate":
            # Ульта доступна только в раунде 3 и с шансом 40%
            if round_num >= 3 and rng.random() < 0.40:
                available.append(m)
        else:
            available.append(m)

    if not available:
        available = [m for m in moves if m["type"] != "ultimate"]

    # Логика выбора
    hp_ratio = own_hp / fighter["hp"] if fighter["hp"] > 0 else 0

    weights = []
    for m in available:
        w = 1.0
        if m["type"] == "light":
            w = 2.0 if hp_ratio > 0.5 else 1.0
        elif m["type"] == "heavy":
            w = 1.5 if hp_ratio < 0.4 else 1.0
        elif m["type"] == "special":
            w = 1.8 if round_num == 2 else 1.2
        elif m["type"] == "ultimate":
            w = 3.0  # если доступна — высокий приоритет
        weights.append(w)

    chosen = rng.choices(available, weights=weights, k=1)[0]
    return chosen


# ── Расчёт урона ─────────────────────────────────────────

def _calc_damage(attacker: dict, defender: dict, move: dict,
                 rng: random.Random, enemy_move_type: str = "") -> tuple[int, bool, str, bool]:
    """Считает урон одного удара. Возвращает (урон, крит?, эффект, контра?)."""
    # Проверка попадания
    acc = move["accuracy"] / 100.0
    # SPD влияет на уклонение
    dodge_bonus = (defender["spd"] - attacker["spd"]) * 0.02
    hit_chance = max(0.20, min(0.98, acc - dodge_bonus))

    if rng.random() > hit_chance:
        return 0, False, "промах", False

    # Базовый урон
    base = move["base_dmg"]
    atk_bonus = attacker["atk"] * 0.5
    def_reduction = defender["def"] * 0.35
    raw = base + atk_bonus - def_reduction



    # Рандом разброс ±15%
    raw *= rng.uniform(0.85, 1.15)

    # Крит
    crit = False
    crit_chance = CRIT_CHANCE + attacker["luck"] * 0.015
    if rng.random() < crit_chance:
        raw *= CRIT_MULT
        crit = True

    # Counter system
    counter = False
    move_type = move.get("type", "")
    if enemy_move_type and move_type in _COUNTER_MAP:
        if _COUNTER_MAP[move_type] == enemy_move_type:
            raw *= 1.3
            counter = True
        elif enemy_move_type in _COUNTER_MAP and _COUNTER_MAP[enemy_move_type] == move_type:
            raw *= 0.8

    dmg = max(MIN_DAMAGE, int(raw))

    # Эффекты
    effect = move.get("effect", "")

    return dmg, crit, effect, counter


# ── Применение эффектов ──────────────────────────────────

def _apply_effect(effect: str, target: dict, source: dict,
                  target_hp: int) -> tuple[dict, int, str]:
    """Применяет эффект и возвращает (изменённые_статы, hp, описание)."""
    desc = ""
    # Копируем чтобы не мутировать оригинал
    t = dict(target)
    if effect == "def_down":
        t["def"] = max(0, t["def"] - 5)
        desc = f"{t['name']}: DEF -5"
    elif effect == "atk_down":
        t["atk"] = max(0, t["atk"] - 5)
        desc = f"{t['name']}: ATK -5"
    elif effect == "atk_up":
        source_copy = dict(source)
        source_copy["atk"] = source_copy["atk"] + 5
        desc = f"{source['name']}: ATK +5"
        return source_copy, target_hp, desc
    elif effect == "def_up":
        source_copy = dict(source)
        source_copy["def"] = source_copy["def"] + 5
        desc = f"{source['name']}: DEF +5"
        return source_copy, target_hp, desc
    elif effect == "spd_up":
        source_copy = dict(source)
        source_copy["spd"] = source_copy["spd"] + 2
        desc = f"{source['name']}: SPD +2"
        return source_copy, target_hp, desc
    elif effect == "spd_down":
        t["spd"] = max(0, t["spd"] - 2)
        desc = f"{t['name']}: SPD -2"
    elif effect == "confuse":
        desc = f"{t['name']} в замешательстве!"
    elif effect == "hp_regen":
        heal = 20
        source_hp = min(source["hp"], target_hp + heal)
        desc = f"{source['name']} восстановил {heal} HP"
        return source, source_hp, desc

    return t, target_hp, desc


# ── Нарратив ─────────────────────────────────────────────

_ROUND_INTROS = [
    "Гонг звучит! Раунд {n} начинается!",
    "Раунд {n}! Арена дрожит!",
    "Раунд {n} — напряжение нарастает!",
]

_CRIT_LINES = [
    "💥 КРИТИЧЕСКИЙ УДАР! {name} наносит сокрушительный {move}!",
    "🔥 КРИТ! {name} попадает идеально — {move}!",
    "⚡ СМЕРТЕЛЬНЫЙ УДАР! {move} от {name} пробивает защиту!",
]

_MISS_LINES = [
    "💨 {name} промахивается с {move}!",
    "🌀 {move} от {name} не попадает в цель!",
    "😤 {name} бьёт мимо — {move} уходит в пустоту!",
]

_HIT_LINES = [
    "{name} наносит {move} — {dmg} урона!",
    "{move} попадает! {name} снимает {dmg} HP!",
    "{name} бьёт {move} на {dmg}!",
]

_WINNER_LINES = [
    "🏆 {name} одерживает победу! {taunt}",
    "🎖️ Победитель — {name}! «{taunt}»",
    "👑 {name} стоит последним на арене! «{taunt}»",
]

_COMBO_LINES = [
    "🔥 COMBO x{n}! {name} в ударе!",
    "💥 {name} — COMBO x{n}! Не остановить!",
]

_COUNTER_LINES = [
    "🛡️ КОНТР-УДАР! {name} читает противника как книгу!",
    "⚡ {name} использует слабость врага! КОНТРА!",
]

# Counter map: light beats special, special beats heavy, heavy beats light
_COUNTER_MAP = {"light": "special", "special": "heavy", "heavy": "light"}


def _narrate_round(rr: RoundResult, fa: dict, fb: dict,
                   rng: random.Random) -> str:
    lines = []
    lines.append(rng.choice(_ROUND_INTROS).format(n=rr.round_num))

    for name, move, dmg, crit, fdata in [
        (fa["name"], rr.fighter_a_move, rr.damage_to_b, rr.crit_a, fa),
        (fb["name"], rr.fighter_b_move, rr.damage_to_a, rr.crit_b, fb),
    ]:
        mname = move["name"]
        if dmg == 0:
            lines.append(rng.choice(_MISS_LINES).format(name=name, move=mname))
        elif crit:
            lines.append(rng.choice(_CRIT_LINES).format(name=name, move=mname))
        else:
            lines.append(rng.choice(_HIT_LINES).format(
                name=name, move=mname, dmg=dmg
            ))

    for eff in [rr.effect_a, rr.effect_b]:
        if eff:
            lines.append(f"  ↳ {eff}")

    lines.append(
        f"  HP: {fa['name']} {rr.hp_a_after} | {fb['name']} {rr.hp_b_after}"
    )
    return "\n".join(lines)


# ── Главная функция боя ──────────────────────────────────

def simulate_fight(
    fighter_a_id: str,
    fighter_b_id: str,
    bet_fighter_id: str,
    bet_amount: int,
    client_seed: str = "",
) -> FightResult:
    """
    Запускает полный бой из 3 раундов.
    Возвращает FightResult со всеми деталями.
    """
    fa_orig = _get_fighter(fighter_a_id)
    fb_orig = _get_fighter(fighter_b_id)
    if not fa_orig or not fb_orig:
        raise ValueError("Боец не найден")
    if fa_orig["id"] == fb_orig["id"]:
        raise ValueError("Нельзя выставить бойца против самого себя")
    if not (MIN_BET <= bet_amount <= MAX_BET):
        raise ValueError(f"Ставка должна быть от {MIN_BET} до {MAX_BET} ₲")
    if bet_fighter_id not in (fa_orig["id"], fb_orig["id"]):
        raise ValueError("Ставка должна быть на одного из бойцов")

    # Provably fair seeds
    server_seed = hashlib.sha256(
        f"{time.time()}{random.random()}".encode()
    ).hexdigest()
    if not client_seed:
        client_seed = hashlib.sha256(
            f"client_{time.time()}".encode()
        ).hexdigest()[:16]
    nonce = int(time.time() * 1000) % 1_000_000

    # RNG из комбинированного сида
    combined = f"{server_seed}:{client_seed}:{nonce}"
    seed_int = int(hashlib.sha256(combined.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed_int)

    # Копии бойцов (чтобы мутировать статы в бою)
    fa = dict(fa_orig)
    fb = dict(fb_orig)

    fight_id = _generate_fight_id()

    # Объективный победитель
    obj_winner_id, obj_prob = compute_objective_winner(fa, fb)

    # House edge: 70% побеждает объективно лучший
    fair_roll = _provably_fair_seed(server_seed, client_seed, nonce)
    if fair_roll < HOUSE_EDGE:
        predetermined_winner = obj_winner_id
    else:
        predetermined_winner = fb["id"] if obj_winner_id == fa["id"] else fa["id"]

    is_upset = predetermined_winner != obj_winner_id

    # Симуляция раундов
    hp_a = fa["hp"]
    hp_b = fb["hp"]
    rounds: list[RoundResult] = []

    for rnd in range(1, ROUNDS + 1):
        move_a = _ai_pick_move(fa, rnd, hp_a, hp_b, rng)
        move_b = _ai_pick_move(fb, rnd, hp_b, hp_a, rng)

        dmg_b, crit_a, eff_a_raw, _ = _calc_damage(fa, fb, move_a, rng, enemy_move_type=move_b.get("type", ""))
        dmg_a, crit_b, eff_b_raw, _ = _calc_damage(fb, fa, move_b, rng, enemy_move_type=move_a.get("type", ""))

        # Применяем урон
        hp_b = max(0, hp_b - dmg_b)
        hp_a = max(0, hp_a - dmg_a)

        # Эффекты
        eff_a_desc = ""
        eff_b_desc = ""
        if eff_a_raw and eff_a_raw != "промах":
            fb, hp_b, eff_a_desc = _apply_effect(eff_a_raw, fb, fa, hp_b)
        if eff_b_raw and eff_b_raw != "промах":
            fa, hp_a, eff_b_desc = _apply_effect(eff_b_raw, fa, fb, hp_a)

        rr = RoundResult(
            round_num=rnd,
            fighter_a_move=move_a,
            fighter_b_move=move_b,
            damage_to_a=dmg_a,
            damage_to_b=dmg_b,
            hp_a_after=hp_a,
            hp_b_after=hp_b,
            crit_a=crit_a,
            crit_b=crit_b,
            effect_a=eff_a_desc,
            effect_b=eff_b_desc,
        )
        rr.narration = _narrate_round(rr, fa, fb, rng)
        rounds.append(rr)

        # Если кто-то умер — бой кончается досрочно
        if hp_a <= 0 or hp_b <= 0:
            break

    # Определяем победителя
    # Если оба живы после 3 раундов — корректируем под predetermined
    if hp_a <= 0 and hp_b <= 0:
        # Оба упали — побеждает predetermined
        winner_id = predetermined_winner
    elif hp_a <= 0:
        winner_id = fb["id"]
    elif hp_b <= 0:
        winner_id = fa["id"]
    else:
        # Оба живы — побеждает predetermined
        # Но делаем это правдоподобно: победитель — тот, у кого больше HP
        # Если predetermined не совпадает — «случайный крит в конце»
        winner_id = predetermined_winner

    # Финальная корректировка HP для нарратива
    if winner_id == fa["id"] and hp_a <= 0:
        hp_a = rng.randint(1, 15)
    elif winner_id == fb["id"] and hp_b <= 0:
        hp_b = rng.randint(1, 15)

    # Ставка
    bet_won = (bet_fighter_id == winner_id)
    payout = int(bet_amount * PAYOUT_MULT) if bet_won else 0

    # Финальный нарратив
    winner_data = fa_orig if winner_id == fa_orig["id"] else fb_orig
    final_narration = rng.choice(_WINNER_LINES).format(
        name=winner_data["name"], taunt=winner_data["taunt"]
    )
    if is_upset:
        final_narration += "\n⚡ НЕОЖИДАННЫЙ ИСХОД! Андердог побеждает!"

    result = FightResult(
        fight_id=fight_id,
        fighter_a=fa_orig,
        fighter_b=fb_orig,
        rounds=rounds,
        winner_id=winner_id,
        objective_winner_id=obj_winner_id,
        is_upset=is_upset,
        narration=final_narration,
        bet_fighter_id=bet_fighter_id,
        bet_amount=bet_amount,
        payout=payout,
        bet_won=bet_won,
        server_seed=hashlib.sha256(server_seed.encode()).hexdigest(),
        client_seed=client_seed,
        nonce=nonce,
    )
    return result


# ── Сериализация для API ─────────────────────────────────

def fight_result_to_dict(r: FightResult) -> dict[str, Any]:
    """Конвертирует FightResult в JSON-безопасный dict."""
    return {
        "fight_id": r.fight_id,
        "fighter_a": {
            "id": r.fighter_a["id"],
            "name": r.fighter_a["name"],
            "name_en": r.fighter_a["name_en"],
            "emoji": r.fighter_a["emoji"],
            "type": r.fighter_a["type"],
            "color": r.fighter_a["color"],
            "gradient": r.fighter_a["gradient"],
            "taunt": r.fighter_a["taunt"],
        },
        "fighter_b": {
            "id": r.fighter_b["id"],
            "name": r.fighter_b["name"],
            "name_en": r.fighter_b["name_en"],
            "emoji": r.fighter_b["emoji"],
            "type": r.fighter_b["type"],
            "color": r.fighter_b["color"],
            "gradient": r.fighter_b["gradient"],
            "taunt": r.fighter_b["taunt"],
        },
        "rounds": [
            {
                "round": rr.round_num,
                "move_a": {"name": rr.fighter_a_move["name"], "type": rr.fighter_a_move["type"]},
                "move_b": {"name": rr.fighter_b_move["name"], "type": rr.fighter_b_move["type"]},
                "damage_to_a": rr.damage_to_a,
                "damage_to_b": rr.damage_to_b,
                "hp_a": rr.hp_a_after,
                "hp_b": rr.hp_b_after,
                "crit_a": rr.crit_a,
                "crit_b": rr.crit_b,
                "effect_a": rr.effect_a,
                "effect_b": rr.effect_b,
                "narration": rr.narration,
            }
            for rr in r.rounds
        ],
        "winner_id": r.winner_id,
        "is_upset": r.is_upset,
        "narration": r.narration,
        "bet": {
            "fighter_id": r.bet_fighter_id,
            "amount": r.bet_amount,
            "payout": r.payout,
            "won": r.bet_won,
        },
        "fairness": {
            "server_seed_hash": r.server_seed,
            "client_seed": r.client_seed,
            "nonce": r.nonce,
        },
    }


# ── Round-by-round бой (юзер выбирает удары) ─────────────

@dataclass
class FightState:
    """Состояние боя для пошагового режима."""
    fight_id: str
    fa: dict
    fb: dict
    fa_orig: dict
    fb_orig: dict
    hp_a: int
    hp_b: int
    current_round: int
    rounds: list[RoundResult]
    predetermined_winner: str
    obj_winner_id: str
    is_upset: bool
    bet_fighter_id: str
    bet_amount: int
    server_seed: str
    client_seed: str
    nonce: int
    rng: random.Random
    user_is_a: bool
    finished: bool = False
    winner_id: str = ""
    combo_a: list = field(default_factory=list)
    combo_b: list = field(default_factory=list)


def create_fight_state(
    fighter_a_id: str,
    fighter_b_id: str,
    bet_fighter_id: str,
    bet_amount: int,
    client_seed: str = "",
) -> FightState:
    """Создаёт состояние боя. Юзер управляет бойцом, на которого поставил."""
    fa_orig = _get_fighter(fighter_a_id)
    fb_orig = _get_fighter(fighter_b_id)
    if not fa_orig or not fb_orig:
        raise ValueError("Боец не найден")
    if fa_orig["id"] == fb_orig["id"]:
        raise ValueError("Нельзя выставить бойца против самого себя")
    if bet_fighter_id not in (fa_orig["id"], fb_orig["id"]):
        raise ValueError("Ставка должна быть на одного из бойцов")

    server_seed = hashlib.sha256(
        f"{time.time()}{random.random()}".encode()
    ).hexdigest()
    if not client_seed:
        client_seed = hashlib.sha256(
            f"client_{time.time()}".encode()
        ).hexdigest()[:16]
    nonce = int(time.time() * 1000) % 1_000_000

    combined = f"{server_seed}:{client_seed}:{nonce}"
    seed_int = int(hashlib.sha256(combined.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed_int)

    fa = dict(fa_orig)
    fb = dict(fb_orig)
    fight_id = _generate_fight_id()

    obj_winner_id, _ = compute_objective_winner(fa, fb)
    fair_roll = _provably_fair_seed(server_seed, client_seed, nonce)
    if fair_roll < HOUSE_EDGE:
        predetermined_winner = obj_winner_id
    else:
        predetermined_winner = fb["id"] if obj_winner_id == fa["id"] else fa["id"]

    return FightState(
        fight_id=fight_id,
        fa=fa, fb=fb,
        fa_orig=fa_orig, fb_orig=fb_orig,
        hp_a=fa["hp"], hp_b=fb["hp"],
        current_round=1,
        rounds=[],
        predetermined_winner=predetermined_winner,
        obj_winner_id=obj_winner_id,
        is_upset=predetermined_winner != obj_winner_id,
        bet_fighter_id=bet_fighter_id,
        bet_amount=bet_amount,
        server_seed=server_seed,
        client_seed=client_seed,
        nonce=nonce,
        rng=rng,
        user_is_a=(bet_fighter_id == fa_orig["id"]),
    )


def get_user_moves(state: FightState) -> tuple[list[dict], str]:
    """Доступные ходы юзера + AI hint (блеф)."""
    uf = state.fa if state.user_is_a else state.fb
    af = state.fb if state.user_is_a else state.fa
    result = []
    for i, m in enumerate(uf["moves"]):
        avail = True
        if m["type"] == "ultimate" and state.current_round < 3:
            avail = False
        result.append({
            "index": i,
            "name": m["name"],
            "type": m["type"],
            "base_dmg": m["base_dmg"],
            "accuracy": m["accuracy"],
            "desc": m.get("desc", ""),
            "available": avail,
        })

    # AI hint (50% truth, 50% bluff)
    type_labels = {"light": "лёгкий удар ⚡", "heavy": "тяжёлый удар 🔨", "special": "спец. приём ✨", "ultimate": "УЛЬТА 💀"}
    ai_move = _ai_pick_move(af, state.current_round,
                            state.hp_b if state.user_is_a else state.hp_a,
                            state.hp_a if state.user_is_a else state.hp_b,
                            random.Random(state.rng.random()))
    real_type = ai_move["type"]
    if state.rng.random() < 0.5:
        hint_type = real_type
    else:
        other_types = [t for t in type_labels if t != real_type]
        hint_type = state.rng.choice(other_types)
    ai_hint = f"Скорее всего противник ударит: {type_labels.get(hint_type, hint_type)}"

    return result, ai_hint


def play_round(state: FightState, user_move_index: int) -> dict:
    """Разыгрывает 1 раунд. Юзер выбирает ход, оппонент — AI."""
    if state.finished:
        raise ValueError("Бой уже окончен")
    if state.current_round > ROUNDS:
        raise ValueError("Все раунды сыграны")

    rnd = state.current_round
    uf = state.fa if state.user_is_a else state.fb
    af = state.fb if state.user_is_a else state.fa

    moves = uf["moves"]
    if user_move_index < 0 or user_move_index >= len(moves):
        raise ValueError("Неверный индекс хода")
    user_move = moves[user_move_index]
    if user_move["type"] == "ultimate" and rnd < 3:
        raise ValueError("Ульта доступна только в раунде 3!")

    # AI для оппонента
    if state.user_is_a:
        ai_move = _ai_pick_move(af, rnd, state.hp_b, state.hp_a, state.rng)
        move_a, move_b = user_move, ai_move
    else:
        ai_move = _ai_pick_move(af, rnd, state.hp_a, state.hp_b, state.rng)
        move_a, move_b = ai_move, user_move

    dmg_b, crit_a, eff_a_raw, counter_a = _calc_damage(state.fa, state.fb, move_a, state.rng, enemy_move_type=move_b.get("type", ""))
    dmg_a, crit_b, eff_b_raw, counter_b = _calc_damage(state.fb, state.fa, move_b, state.rng, enemy_move_type=move_a.get("type", ""))

    # Combo tracking
    state.combo_a.append(move_a.get("type", ""))
    state.combo_b.append(move_b.get("type", ""))

    def _combo_count(combo_list):
        if len(combo_list) < 2:
            return 1
        streak = 1
        for j in range(len(combo_list) - 1, 0, -1):
            if combo_list[j] == combo_list[j - 1]:
                streak += 1
            else:
                break
        return streak

    combo_a_count = _combo_count(state.combo_a)
    combo_b_count = _combo_count(state.combo_b)

    if combo_a_count >= 3:
        dmg_b = int(dmg_b * 1.6)
    elif combo_a_count >= 2:
        dmg_b = int(dmg_b * 1.3)

    if combo_b_count >= 3:
        dmg_a = int(dmg_a * 1.6)
    elif combo_b_count >= 2:
        dmg_a = int(dmg_a * 1.3)

    state.hp_b = max(0, state.hp_b - dmg_b)
    state.hp_a = max(0, state.hp_a - dmg_a)

    eff_a_desc = ""
    eff_b_desc = ""
    if eff_a_raw and eff_a_raw != "промах":
        state.fb, state.hp_b, eff_a_desc = _apply_effect(eff_a_raw, state.fb, state.fa, state.hp_b)
    if eff_b_raw and eff_b_raw != "промах":
        state.fa, state.hp_a, eff_b_desc = _apply_effect(eff_b_raw, state.fa, state.fb, state.hp_a)

    rr = RoundResult(
        round_num=rnd,
        fighter_a_move=move_a,
        fighter_b_move=move_b,
        damage_to_a=dmg_a,
        damage_to_b=dmg_b,
        hp_a_after=state.hp_a,
        hp_b_after=state.hp_b,
        crit_a=crit_a,
        crit_b=crit_b,
        effect_a=eff_a_desc,
        effect_b=eff_b_desc,
    )
    rr.narration = _narrate_round(rr, state.fa, state.fb, state.rng)

    # Add combo narration
    if combo_a_count >= 2:
        rr.narration += "\n" + state.rng.choice(_COMBO_LINES).format(n=combo_a_count, name=state.fa["name"])
    if combo_b_count >= 2:
        rr.narration += "\n" + state.rng.choice(_COMBO_LINES).format(n=combo_b_count, name=state.fb["name"])
    if counter_a:
        rr.narration += "\n" + state.rng.choice(_COUNTER_LINES).format(name=state.fa["name"])
    if counter_b:
        rr.narration += "\n" + state.rng.choice(_COUNTER_LINES).format(name=state.fb["name"])

    state.rounds.append(rr)
    state.current_round += 1

    fight_over = state.hp_a <= 0 or state.hp_b <= 0 or state.current_round > ROUNDS

    rd = {
        "round": rr.round_num,
        "move_a": {"name": rr.fighter_a_move["name"], "type": rr.fighter_a_move["type"]},
        "move_b": {"name": rr.fighter_b_move["name"], "type": rr.fighter_b_move["type"]},
        "damage_to_a": rr.damage_to_a,
        "damage_to_b": rr.damage_to_b,
        "hp_a": rr.hp_a_after,
        "hp_b": rr.hp_b_after,
        "crit_a": rr.crit_a,
        "crit_b": rr.crit_b,
        "effect_a": rr.effect_a,
        "effect_b": rr.effect_b,
        "narration": rr.narration,
        "fight_over": fight_over,
        "combo_a": combo_a_count if combo_a_count >= 2 else 0,
        "combo_b": combo_b_count if combo_b_count >= 2 else 0,
        "counter_a": counter_a,
        "counter_b": counter_b,
    }

    if fight_over:
        state.finished = True
        final = _finalize_fight(state)
        rd["result"] = fight_result_to_dict(final)
    else:
        moves, ai_hint = get_user_moves(state)
        rd["next_moves"] = moves
        rd["ai_hint"] = ai_hint

    return rd


def _finalize_fight(state: FightState) -> FightResult:
    """Определяет победителя и собирает FightResult."""
    hp_a, hp_b = state.hp_a, state.hp_b

    if hp_a <= 0 and hp_b <= 0:
        winner_id = state.predetermined_winner
    elif hp_a <= 0:
        winner_id = state.fb["id"]
    elif hp_b <= 0:
        winner_id = state.fa["id"]
    else:
        winner_id = state.predetermined_winner

    if winner_id == state.fa["id"] and hp_a <= 0:
        hp_a = state.rng.randint(1, 15)
    elif winner_id == state.fb["id"] and hp_b <= 0:
        hp_b = state.rng.randint(1, 15)

    bet_won = (state.bet_fighter_id == winner_id)
    payout = int(state.bet_amount * PAYOUT_MULT) if bet_won else 0

    winner_data = state.fa_orig if winner_id == state.fa_orig["id"] else state.fb_orig
    final_narration = state.rng.choice(_WINNER_LINES).format(
        name=winner_data["name"], taunt=winner_data["taunt"]
    )
    if state.is_upset:
        final_narration += "\n⚡ НЕОЖИДАННЫЙ ИСХОД! Андердог побеждает!"

    return FightResult(
        fight_id=state.fight_id,
        fighter_a=state.fa_orig,
        fighter_b=state.fb_orig,
        rounds=state.rounds,
        winner_id=winner_id,
        objective_winner_id=state.obj_winner_id,
        is_upset=state.is_upset,
        narration=final_narration,
        bet_fighter_id=state.bet_fighter_id,
        bet_amount=state.bet_amount,
        payout=payout,
        bet_won=bet_won,
        server_seed=hashlib.sha256(state.server_seed.encode()).hexdigest(),
        client_seed=state.client_seed,
        nonce=state.nonce,
    )
