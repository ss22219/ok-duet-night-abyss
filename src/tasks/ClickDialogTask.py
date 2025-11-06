from ok import TriggerTask, Logger
from src.tasks.BaseDNATask import BaseDNATask

logger = Logger.get_logger(__name__)

class ClickDialogTask(BaseDNATask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自动肉鸽对话"
        self.description = "自动点击肉鸽对话"
        self.template_shape = None
    
    def run(self):
        if self.in_team():
            return
        if self.template_shape != self.frame.shape[:2]:
            self.init_box()
        rogue_dialogs = self.find_feature("rogue_dialog", box=self.rogue_dialog_box)
        rogue_gift = self.find_one("rogue_gift", box=self.rogue_dialog_box)
        if (len(rogue_dialogs) == 1 and not rogue_gift):
            self.click_box(rogue_dialogs)

    def init_box(self):
        self.rogue_dialog_box = self.box_of_screen_scaled(2560, 1440, 1504, 854, 1555, 1224, name="rogue_dialog", hcenter=True)
        self.template_shape = self.frame.shape[:2]



