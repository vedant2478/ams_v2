class Instance:

    def __init__(self, instance_name=None, next=None, prev=None):
        self.instance_name = instance_name
        self.next = next
        self.prev = prev


class InstanceDoublyLinkedList:

    def __init__(self):
        self.head = Instance()

    def append(self, name):
        new_instance = Instance(instance_name=name)
        if self.head.instance_name is None:
            self.head = new_instance
            self.head.prev = new_instance
            self.head.next = new_instance
            return
        current_instance = self.head
        while current_instance.next != self.head:
            current_instance = current_instance.next
        new_instance.next = self.head
        current_instance.next = new_instance
        new_instance.prev = current_instance
        self.head.prev = new_instance

    def print_list(self):
        elements = []
        current_instance = self.head
        while current_instance:
            elements.append(current_instance.instance_name)
            current_instance = current_instance.next
            if current_instance == self.head:
                break
        return elements

    def length(self):
        current_instance = self.head
        count = 0
        while current_instance:
            count += 1
            current_instance = current_instance.next
            if current_instance == self.head:
                break
        return count
