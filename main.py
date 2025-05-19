from collections import OrderedDict

class MRUCache:
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = value
        else:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=True)
            self.cache[key] = value

mru = MRUCache(2)
mru.put(1, 1)
mru.put(2, 2)
mru.get(1)
mru.put(3, 3)
print(mru.get(1))
print(mru.get(2))

