from datetime import datetime


class YearConfig:

    def __init__(self):
        today = datetime.today()
        self.SYSTEM_YEAR = today.year + (1 if today.month == 12 else 0)

    def get_formatted_date(self):
        today = datetime.today()
        return f"🕐 {today.year}. {today.month}. {today.day}."

    def set_system_year(self, year: int):
        self.SYSTEM_YEAR = year


yearConfig = YearConfig()
