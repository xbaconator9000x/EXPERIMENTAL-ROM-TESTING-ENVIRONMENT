import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch
from core.upstream_shop import ReadOnlyShopMixin
from core.upstream_leafgreen.state import GameContext

class Shop(ReadOnlyShopMixin):
    _MART_CLERK_APPROACH=(2,4)
    def __init__(self,stock=(4,13),interactive=True):
        self.context=GameContext.OVERWORLD
        self.stock=stock;self.interactive=interactive;self.inputs=[];self.committed=False
        self.reader=SimpleNamespace(read_player_pos=lambda:(2,4),read_current_map=lambda:(1,2),detect_context=lambda:self.context)
        self.mgba=SimpleNamespace(tap=self.tap,tick=lambda n:None)
    def tap(self,b):
        self.inputs.append(b)
        if b=="A":
            if self.context==GameContext.OVERWORLD:self.context=GameContext.DIALOG_OPEN
            else:self.committed=True;self.context=GameContext.IN_MENU
    def _walk_to(self,*target):pass
    def _wait_idle(self):pass
    def _buy_list_open(self):return True
    def _shop_item_list(self):return self.stock
    def _buy_list_interactive(self):return self.interactive
    def _menus(self):return SimpleNamespace(menu_cursor=lambda:0,choice_live=lambda:True)
class ReadOnlyShopTests(unittest.TestCase):
    def test_verified_counter_and_stock(self):
        modules={"game.state":SimpleNamespace(GameContext=GameContext),"knowledge.shop_stock":SimpleNamespace(SHOPS=[(1,2,2,3,(4,13))])}
        with patch.dict(sys.modules,modules):
            f=Shop();self.assertTrue(f._open_buy_menu());self.assertEqual(f.inputs,["Up","A","A"])
            f=Shop(stock=(99,));self.assertFalse(f._open_buy_menu());self.assertFalse(f.committed)
            f=Shop(interactive=False);self.assertFalse(f._open_buy_menu())
            f=Shop();self.assertFalse(f._open_buy_menu(sell=True));self.assertFalse(f.inputs)
