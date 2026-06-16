from time import time 
from anyblok import start


startt = time()
registry = start(
    'default',
    entry_points=('bloks', 'test_bloks'),
    loadwithoutmigration=True,
)
endt = time()
print(f"started time: {(endt - startt)} : {registry}")
print(registry.System.Blok)
print(registry.System.Blok.query().order_by(registry.System.Blok.order).all())
print(registry.System.Blok)
print(len(registry.loaded_namespaces))
