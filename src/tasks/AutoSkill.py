from qfluentwidgets import FluentIcon
import time
import cv2
import re

from ok import Logger, TaskDisabledException
from src.tasks.BaseCombatTask import BaseCombatTask
from src.tasks.DNAOneTimeTask import DNAOneTimeTask
from src.tasks.CommissionsTask import CommissionsTask

logger = Logger.get_logger(__name__)


class AutoSkill(DNAOneTimeTask, BaseCombatTask, CommissionsTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        #  self.description = "使用水母姐"
        self.default_config.update({
            '使用技能': '不使用',
            '技能释放频率': 5,
            '任务超时时间': 120,
            '主画面侦测': True,
            '发出声音提醒': True,
        })
        self.config_type['使用技能'] = {'type': 'drop_down', 'options': ['不使用', '战技', '终结技']}
        self.config_description = {
            '技能释放频率': '毎几秒释放一次技能',
            '主画面侦测': '如果不在可操控角色的画面则结束任务',
            '任务超时时间': '放弃任务前等待的秒数',
            '发出声音提醒': '在需要时发出声音提醒',
        }
        
        self.name = "自动释放技能"
        self.action_timeout = 10
        
    def run(self):
        DNAOneTimeTask.run(self)
        try:
            return self.do_run()
        except TaskDisabledException as e:
            pass
        except Exception as e:
            logger.error('AutoCombatSkill error', e)
            raise

    def do_run(self):
        self.load_char()
        _skill_time = 0
        self.wait_until(self.in_team, time_out=30)
        while True:
            if self.in_team():
                _skill_time = self.use_skill(_skill_time)
            else:
                if self.config.get('主画面侦测', False):
                    self.log_info('任务完成', notify=True)
                    self.soundBeep()
                    return
            if time.time() - self.start_time >= self.config.get('任务超时时间', 120):
                self.log_info('任务超时', notify=True)
                self.soundBeep()
                return
            self.sleep(0.2)
