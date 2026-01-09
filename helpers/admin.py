def admin_meta(**meta):
    def decorator(func):
        func.admin_help = meta
        return func
    return decorator