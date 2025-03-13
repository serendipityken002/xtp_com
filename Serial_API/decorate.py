from functools import wraps

"""
python中
1. 直接使用函数名，那么这个函数可以被传递。如果在后面加上括号，那么这个函数就会被调用。
2. wraps的作用：保留原函数的元信息，否则被装饰的函数会变化成装饰器函数的元信息
3. 装饰器的作用：在不改变原函数的情况下，增加新的功能
"""

def hi(name='lihua'):
    def hello():
        print(f"Hello {name}!")
    def welcome():
        print(f"Welcome {name}!")

    if name == 'lihua':
        return hello
    else:
        return welcome

def decorate_name(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        print(f"装饰器装饰函数 {f.__name__}")
        username = "admin"
        return f(username, *args, **kwargs)
    return decorated

@decorate_name
def register(username):
    print(f"注册用户 {username}")

register()
print(register.__name__)