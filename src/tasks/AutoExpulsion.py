from qfluentwidgets import FluentIcon
import time

from ok import Logger, TaskDisabledException
from src.tasks.DNAOneTimeTask import DNAOneTimeTask
from src.tasks.CommissionsTask import CommissionsTask, Mission
from src.tasks.BaseCombatTask import BaseCombatTask

logger = Logger.get_logger(__name__)


class AutoExpulsion(DNAOneTimeTask, CommissionsTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.description = "全自动"
        self.default_config.update({
            '开局向前走': 0,
            '任务超时时间': 120,
            '刷几次': 999,
        })
        self.config_description.update({
            '开局向前走': '开局向前走几秒',
            '任务超时时间': '放弃任务前等待的秒数',
        })
        self.setup_commission_config()
        self.default_config.pop('启用自动穿引共鸣', None)
        self.name = "自动驱离"
        self.action_timeout = 10
        
    def run(self):
        DNAOneTimeTask.run(self)
        try:
            return self.do_run()
        except TaskDisabledException as e:
            pass
        except Exception as e:
            logger.error('AutoExpulsion error', e)
            raise

    def do_run(self):
        self.load_char()
        _start_time = 0
        _skill_time = 0
        _count = 0
        while True:
            if self.in_team():
                if _start_time == 0:
                    _start_time = time.time()
                _skill_time = self.use_skill(_skill_time)
                if time.time() - _start_time >= self.config.get('任务超时时间', 120):
                    logger.info("已经超时，重开任务...")
                    self.give_up_mission()
                    self.wait_until(lambda: not self.in_team(), time_out=30)

            _status = self.handle_mission_interface()
            if _status == Mission.START:
                self.log_info('任务完成')
                _count += 1
                if _count >= self.config.get('刷几次', 999):
                    return
                self.wait_until(self.in_team, time_out=30)
                _start_time = time.time()
                if (walk_sec:=self.config.get('开局向前走', 0)) > 0:
                    self.send_key('w', down_time=walk_sec)
            self.sleep(0.2)
