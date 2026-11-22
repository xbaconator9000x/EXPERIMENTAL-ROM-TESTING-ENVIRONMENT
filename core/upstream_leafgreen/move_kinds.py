"""Extracted verbatim classification from upstream knowledge/move_semantics.py.
MIT: see LICENSE. Source 594bfc7e3c208890c248269b67c5a1cf95074965; only unused role descriptions and scoring omitted.
"""
_KIND: dict[str, str] = {}


def _k(kind: str, *effects: str) -> None:
    for e in effects:
        _KIND[e] = kind


_k("ohko", "OHKO")
_k("fixed", "LEVEL_DAMAGE", "DRAGON_RAGE", "SONICBOOM", "PSYWAVE", "SUPER_FANG")
_k("reactive", "COUNTER", "MIRROR_COAT", "BIDE", "ENDEAVOR", "REVENGE")
_k("req_foe_asleep", "DREAM_EATER")
_k("req_user_asleep", "SNORE", "SLEEP_TALK")
_k("charge", "SOLAR_BEAM", "RAZOR_WIND", "SKULL_BASH", "SKY_ATTACK")
_k("semi_inv", "SEMI_INVULNERABLE")
_k("focus", "FOCUS_PUNCH")
_k("recharge", "RECHARGE")
_k("friend_high", "RETURN")
_k("friend_low", "FRUSTRATION")
_k("flail", "FLAIL")
_k("eruption", "ERUPTION")
_k("hidden_power", "HIDDEN_POWER")
_k("suicide", "EXPLOSION")
_k("false_swipe", "FALSE_SWIPE")
_k("trap_dmg", "TRAP")
_k("future", "FUTURE_SIGHT")
_k("multi", "MULTI_HIT", "DOUBLE_HIT", "TWINEEDLE", "TRIPLE_KICK", "BEAT_UP")
_k("recoil", "RECOIL", "DOUBLE_EDGE", "RECOIL_IF_MISS")
_k("rampage", "RAMPAGE", "UPROAR", "ROLLOUT", "RAGE")
# non-damaging roles
_k("mean_look", "MEAN_LOOK")
_k("protect", "PROTECT", "ENDURE")
_k("force_switch", "ROAR")
_k("teleport", "TELEPORT")
_k("noop", "SPLASH")
_k("sleep", "SLEEP", "YAWN")
_k("para", "PARALYZE")
_k("poison", "POISON", "TOXIC")
_k("burn", "WILL_O_WISP")
_k("confuse", "CONFUSE", "SWAGGER", "FLATTER", "TEETER_DANCE")
_k("disable", "DISABLE", "ENCORE", "TAUNT", "TORMENT", "SPITE", "IMPRISON")
_k("heal", "RESTORE_HP", "SOFTBOILED", "MOONLIGHT", "MORNING_SUN", "SYNTHESIS", "SWALLOW")
_k("rest", "REST")
_k("setup", "ATTACK_UP", "ATTACK_UP_2", "DEFENSE_UP", "DEFENSE_UP_2", "SPECIAL_ATTACK_UP", "SPECIAL_ATTACK_UP_2",
   "SPECIAL_DEFENSE_UP_2", "SPEED_UP_2", "BULK_UP", "CALM_MIND", "DRAGON_DANCE", "COSMIC_POWER", "BELLY_DRUM",
   "DEFENSE_CURL", "MINIMIZE", "EVASION_UP", "FOCUS_ENERGY", "CHARGE", "STOCKPILE", "CURSE")
_k("debuff", "ATTACK_DOWN", "ATTACK_DOWN_2", "DEFENSE_DOWN", "DEFENSE_DOWN_2", "SPEED_DOWN", "SPEED_DOWN_2",
   "SPECIAL_DEFENSE_DOWN_2", "ACCURACY_DOWN", "EVASION_DOWN", "TICKLE")
_k("screen", "LIGHT_SCREEN", "REFLECT", "SAFEGUARD", "MIST")
_k("seed", "LEECH_SEED")
_k("substitute", "SUBSTITUTE")
_k("doom", "DESTINY_BOND", "PERISH_SONG", "GRUDGE", "MEMENTO")
_k("weather", "RAIN_DANCE", "SUNNY_DAY", "SANDSTORM", "HAIL")

