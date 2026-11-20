"""Use upstream move classification with exact local ROM row witnesses."""
import re
from core.upstream_leafgreen.move_effects import MOVE_FX
from core.upstream_leafgreen.move_kinds import _KIND
from core.upstream_leafgreen.type_chart import get_effectiveness

# Source: pret/pokefirered @ ce6406d8c2eaf46d543c8a2606de0c3cb1951982,
# include/constants/battle_move_effects.h, numeric effect IDs only.
EFFECT_IDS={"HIT":0,"SLEEP":1,"POISON_HIT":2,"ABSORB":3,"BURN_HIT":4,"FREEZE_HIT":5,"PARALYZE_HIT":6,"EXPLOSION":7,"DREAM_EATER":8,"MIRROR_MOVE":9,"ATTACK_UP":10,"DEFENSE_UP":11,"SPEED_UP":12,"SPECIAL_ATTACK_UP":13,"SPECIAL_DEFENSE_UP":14,"ACCURACY_UP":15,"EVASION_UP":16,"ALWAYS_HIT":17,"ATTACK_DOWN":18,"DEFENSE_DOWN":19,"SPEED_DOWN":20,"SPECIAL_ATTACK_DOWN":21,"SPECIAL_DEFENSE_DOWN":22,"ACCURACY_DOWN":23,"EVASION_DOWN":24,"HAZE":25,"BIDE":26,"RAMPAGE":27,"ROAR":28,"MULTI_HIT":29,"CONVERSION":30,"FLINCH_HIT":31,"RESTORE_HP":32,"TOXIC":33,"PAY_DAY":34,"LIGHT_SCREEN":35,"TRI_ATTACK":36,"REST":37,"OHKO":38,"RAZOR_WIND":39,"SUPER_FANG":40,"DRAGON_RAGE":41,"TRAP":42,"HIGH_CRITICAL":43,"DOUBLE_HIT":44,"RECOIL_IF_MISS":45,"MIST":46,"FOCUS_ENERGY":47,"RECOIL":48,"CONFUSE":49,"ATTACK_UP_2":50,"DEFENSE_UP_2":51,"SPEED_UP_2":52,"SPECIAL_ATTACK_UP_2":53,"SPECIAL_DEFENSE_UP_2":54,"ACCURACY_UP_2":55,"EVASION_UP_2":56,"TRANSFORM":57,"ATTACK_DOWN_2":58,"DEFENSE_DOWN_2":59,"SPEED_DOWN_2":60,"SPECIAL_ATTACK_DOWN_2":61,"SPECIAL_DEFENSE_DOWN_2":62,"ACCURACY_DOWN_2":63,"EVASION_DOWN_2":64,"REFLECT":65,"POISON":66,"PARALYZE":67,"ATTACK_DOWN_HIT":68,"DEFENSE_DOWN_HIT":69,"SPEED_DOWN_HIT":70,"SPECIAL_ATTACK_DOWN_HIT":71,"SPECIAL_DEFENSE_DOWN_HIT":72,"ACCURACY_DOWN_HIT":73,"EVASION_DOWN_HIT":74,"SKY_ATTACK":75,"CONFUSE_HIT":76,"TWINEEDLE":77,"VITAL_THROW":78,"SUBSTITUTE":79,"RECHARGE":80,"RAGE":81,"MIMIC":82,"METRONOME":83,"LEECH_SEED":84,"SPLASH":85,"DISABLE":86,"LEVEL_DAMAGE":87,"PSYWAVE":88,"COUNTER":89,"ENCORE":90,"PAIN_SPLIT":91,"SNORE":92,"CONVERSION_2":93,"LOCK_ON":94,"SKETCH":95,"UNUSED_60":96,"SLEEP_TALK":97,"DESTINY_BOND":98,"FLAIL":99,"SPITE":100,"FALSE_SWIPE":101,"HEAL_BELL":102,"QUICK_ATTACK":103,"TRIPLE_KICK":104,"THIEF":105,"MEAN_LOOK":106,"NIGHTMARE":107,"MINIMIZE":108,"CURSE":109,"UNUSED_6E":110,"PROTECT":111,"SPIKES":112,"FORESIGHT":113,"PERISH_SONG":114,"SANDSTORM":115,"ENDURE":116,"ROLLOUT":117,"SWAGGER":118,"FURY_CUTTER":119,"ATTRACT":120,"RETURN":121,"PRESENT":122,"FRUSTRATION":123,"SAFEGUARD":124,"THAW_HIT":125,"MAGNITUDE":126,"BATON_PASS":127,"PURSUIT":128,"RAPID_SPIN":129,"SONICBOOM":130,"UNUSED_83":131,"MORNING_SUN":132,"SYNTHESIS":133,"MOONLIGHT":134,"HIDDEN_POWER":135,"RAIN_DANCE":136,"SUNNY_DAY":137,"DEFENSE_UP_HIT":138,"ATTACK_UP_HIT":139,"ALL_STATS_UP_HIT":140,"UNUSED_8D":141,"BELLY_DRUM":142,"PSYCH_UP":143,"MIRROR_COAT":144,"SKULL_BASH":145,"TWISTER":146,"EARTHQUAKE":147,"FUTURE_SIGHT":148,"GUST":149,"FLINCH_MINIMIZE_HIT":150,"SOLAR_BEAM":151,"THUNDER":152,"TELEPORT":153,"BEAT_UP":154,"SEMI_INVULNERABLE":155,"DEFENSE_CURL":156,"SOFTBOILED":157,"FAKE_OUT":158,"UPROAR":159,"STOCKPILE":160,"SPIT_UP":161,"SWALLOW":162,"UNUSED_A3":163,"HAIL":164,"TORMENT":165,"FLATTER":166,"WILL_O_WISP":167,"MEMENTO":168,"FACADE":169,"FOCUS_PUNCH":170,"SMELLINGSALT":171,"FOLLOW_ME":172,"NATURE_POWER":173,"CHARGE":174,"TAUNT":175,"HELPING_HAND":176,"TRICK":177,"ROLE_PLAY":178,"WISH":179,"ASSIST":180,"INGRAIN":181,"SUPERPOWER":182,"MAGIC_COAT":183,"RECYCLE":184,"REVENGE":185,"BRICK_BREAK":186,"YAWN":187,"KNOCK_OFF":188,"ENDEAVOR":189,"ERUPTION":190,"SKILL_SWAP":191,"IMPRISON":192,"REFRESH":193,"GRUDGE":194,"SNATCH":195,"LOW_KICK":196,"SECRET_POWER":197,"DOUBLE_EDGE":198,"TEETER_DANCE":199,"BLAZE_KICK":200,"MUD_SPORT":201,"POISON_FANG":202,"WEATHER_BALL":203,"OVERHEAT":204,"TICKLE":205,"COSMIC_POWER":206,"SKY_UPPERCUT":207,"BULK_UP":208,"POISON_TAIL":209,"WATER_SPORT":210,"CALM_MIND":211,"DRAGON_DANCE":212,"CAMOUFLAGE":213}
def norm(s):
    return re.sub(r"[^A-Z0-9]","",s.upper())
FX={norm(name): data[0] for name,data in MOVE_FX.items()}
TYPES=dict(zip(("normal","fire","water","electric","grass","ice","fighting","poison","ground","flying","psychic","bug","rock","ghost","dragon","dark","steel"),
               "NOR FIR WAT ELE GRS ICE FIG POI GRD FLY PSY BUG ROC GHO DRG DRK STL".split()))

def witnessed_kind(row):
    # Do not identify a hack's modified moves solely by the displayed name.
    effect=FX.get(norm(row.get("name","")))
    if effect not in EFFECT_IDS or row.get("effect")!=EFFECT_IDS[effect]:
        return None
    return _KIND.get(effect,"damage")

def classic_multiplier(attack,defenders):
    if attack not in TYPES or not defenders or any(t not in TYPES for t in defenders):
        return None
    result=1.0
    for t in set(defenders):
        result*=get_effectiveness(TYPES[attack],TYPES[t])
    return result

def safe_damage_kind(row,enemy_status,capture=False):
    kind=witnessed_kind(row)
    # Preserve support for old synthetic rows; real catalog rows carry effects.
    if kind is None:return "damage" if "effect" not in row else None
    if kind in ("ohko","reactive","req_user_asleep","focus","suicide","force_switch","teleport","doom","hidden_power","friend_high","friend_low","flail","eruption","fixed"):
        return None
    if kind=="req_foe_asleep" and not enemy_status&7:return None
    if capture and kind in ("multi","recoil","rampage","trap_dmg","future","charge","semi_inv","recharge"):
        return None
    return kind

def catch_setup_slot(own,enemy,rows,disabled):
    # Upstream catch_setup_hint ordering: False Swipe, sleep, paralysis.
    # Skip status on an already-statused foe, and immunity based on ROM types.
    choices=[]
    for slot,mid in enumerate(own["moves"]):
        row=rows.get(mid,{})
        kind=witnessed_kind(row)
        if not own["pp"][slot] or mid==disabled or kind not in ("false_swipe","sleep","para"):
            continue
        if kind!="false_swipe" and enemy["status"]:continue
        if kind=="false_swipe" and enemy["hp"]<=1:continue
        if kind=="sleep" and FX.get(norm(row.get("name","")))=="YAWN":continue
        if not classic_multiplier(row.get("type"),enemy["types"]):continue
        if kind=="para" and row.get("type")=="electric" and "ground" in enemy["types"]:continue
        choices.append(({"false_swipe":0,"sleep":1,"para":2}[kind],slot))
    return min(choices)[1] if choices else None
