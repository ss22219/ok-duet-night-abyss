from ok import TriggerTask, Logger
from src.tasks.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException

from pynput import mouse
logger = Logger.get_logger(__name__)

class AutoCombatTask(BaseCombatTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自动战斗"
        self.description = "需使用鼠标侧键主动激活"
        self.default_config.update({
            '激活键': 'x2',
        })
        self.config_type['激活键'] = {'type': 'drop_down', 'options': ['x1', 'x2']}
        self.config_description.update({
            '激活键': '鼠标侧键',
        })
        self.listener = None
        self.manual_in_combat = False

    def disable(self):
        super().disable()
        self.stop_listener()

    def pause(self):
        super().pause()
        self.stop_listener()

    def on_destroy(self):
        super().on_destroy()
        self.stop_listener()

    def stop_listener(self):
        self.manual_activate = False
        if self.listener:
            self.listener.stop()
            self.listener = None
    
    def run(self):
        ret = False
        if not self.in_team():
            return ret
        
        if not self.listener:
            self.listener = mouse.Listener(on_click=self.on_click)
            self.listener.start()

        if not self.listener.running:
            self.listener.run()

        while self.in_combat():
            ret = True
            try:
                self.get_current_char().perform()
            except CharDeadException:
                self.log_error(f'Characters dead', notify=True)
                break
            except NotInCombatException as e:
                logger.info(f'auto_combat_task_out_of_combat {e}')
                break
            
        if ret:
            self.combat_end()
        return ret
        
    def on_click(self, x, y, button, pressed):
        if self.executor.paused:
            return
        if self.config.get('激活键', 'x2') == 'x1':
            btn = mouse.Button.x1
        else:
            btn = mouse.Button.x2
        if pressed and button == btn:
            self.manual_in_combat = not self.manual_in_combat



