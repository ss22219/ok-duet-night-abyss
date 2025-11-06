from ok import TriggerTask, Logger, og
from src.tasks.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException

from pynput import mouse
logger = Logger.get_logger(__name__)

class TriggerDeactivateException(Exception):
    """未处于战斗状态异常。"""
    pass

class AutoMoveTask(BaseCombatTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自动穿引共鸣"
        self.description = "需使用鼠标侧键主动激活"
        self.default_config.update({
            '激活键': 'x1',
            '按下时间': 0.50,
            '间隔时间': 0.45,
        })
        self.config_type['激活键'] = {'type': 'drop_down', 'options': ['x1', 'x2']}
        self.config_description.update({
            '激活键': '鼠标侧键',
            '按下时间': '左键按住多久',
            '间隔时间': '左键释放后等待多久',
        })
        self.listener = None
        self.manual_activate = False
        self.is_down = False

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

        while self.manual_activate:
            ret = True
            try:
                self.do_move()
            except CharDeadException:
                self.log_error(f'Characters dead', notify=True)
                break
            except TriggerDeactivateException as e:
                logger.info(f'auto_move_task_deactivate {e}')
                break
            if self.is_down:
                self.mouse_up()
                self.is_down = False
        
        return ret
    
    def do_move(self):
        self.is_down = True
        self.mouse_down()
        self.sleep_check(self.config.get('按下时间', 0.50))
        self.mouse_up()
        self.is_down = False
        self.sleep_check(self.config.get('间隔时间', 0.45))

    def sleep_check(self, sec):
        remaining = sec
        step = 0.25
        while remaining > 0:
            s = step if remaining > step else remaining
            self.sleep(s)
            remaining -= s
            if not self.manual_activate:
                raise TriggerDeactivateException()
        
    def on_click(self, x, y, button, pressed):
        if not self.in_team() or not og.device_manager.hwnd_window.is_foreground():
            return
        if self.config.get('激活键', 'x2') == 'x1':
            btn = mouse.Button.x1
        else:
            btn = mouse.Button.x2
        if pressed and button == btn:
            self.manual_activate = not self.manual_activate
            if self.manual_activate:
                logger.info("激活快速移动")
            else:
                logger.info("关闭快速移动")



