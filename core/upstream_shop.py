"""Input-only override for the pinned upstream _open_buy_menu skill.

The upstream method zeroes a shop-list pointer to invalidate stale memory.
Instead, require a live shop choice, expected stock and a second cursor witness.
All purchase selection, quantities, inventory verification and travel remain
the actual upstream implementation. Refuse ambiguous/one-row menus.
"""
from core.upstream_leafgreen.constants import Addr
from core.upstream_skills import SkillAbort

class ReadOnlyShopMixin:
    def _open_buy_menu(self, approach=None, face="Up", sell=False):
        from game.state import GameContext
        from knowledge.shop_stock import SHOPS
        if sell:
            return False
        target=tuple(approach or self._MART_CLERK_APPROACH)
        self._walk_to(*target)
        if tuple(self.reader.read_player_pos())!=target or self.reader.detect_context()!=GameContext.OVERWORLD:
            return False
        bank,mapid=self.reader.read_current_map()
        stocks=[set(items) for b,m,x,y,items in SHOPS if (b,m)==(bank,mapid)]
        if not stocks:
            return False
        self.mgba.tap(face)
        if tuple(self.reader.read_player_pos())!=target or self.reader.detect_context()!=GameContext.OVERWORLD:
            return False
        # Press A only on the known counter-facing tile; once dialogue starts,
        # require the real shop stock and a reversible choice cursor probe.
        for _ in range(12):
            context=self.reader.detect_context()
            if context==GameContext.IN_BATTLE or tuple(self.reader.read_current_map())!=(bank,mapid):
                return False
            if context in (GameContext.DIALOG_OPEN,GameContext.IN_MENU) and self._buy_list_open():
                listed=set(self._shop_item_list())
                if listed and listed not in stocks:
                    return False
                if listed and listed in stocks:
                    before=self._menus().menu_cursor()
                    if before==0 and self._menus().choice_live():
                        if self._menus().menu_cursor()!=0:
                            return False
                        self.mgba.tap("A")
                        self._wait_idle()
                        self.mgba.tick(40)
                        # No item confirmation before the actual list responds.
                        if not self._buy_list_open() or not self._buy_list_interactive():
                            return False
                        return True
            if context not in (GameContext.OVERWORLD,GameContext.DIALOG_OPEN):
                return False
            self.mgba.tap("A")
            self._wait_idle()
            self.mgba.tick(12)
        return False
