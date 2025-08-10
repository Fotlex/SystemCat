from datetime import timedelta # ### НОВОЕ: Импортируем timedelta


def format_duration(td: timedelta | None):
    if not isinstance(td, timedelta):
        return ""
    
    days = td.days
    seconds = td.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    return f"{days} дн. {hours} ч. {minutes} мин."
