# card_reader_helper.py
from time import sleep
from hw_init import amsbms

def read_card_from_hardware(timeout_seconds=15):
    """
    Poll amsbms.cardNo every 0.25s for up to timeout_seconds.
    Returns card_no (int) or 0 if timeout.
    """
    iterations = timeout_seconds * 4  # 0.25s per iteration
    
    for i in range(iterations):
        sleep(0.25)
        card_no = amsbms.cardNo
        
        print(f"Card poll {i+1}/{iterations}: {card_no}")
        
        if int(card_no) > 0:
            print(f"✓ Card detected: {card_no}")
            return int(card_no)
    
    print("✗ Card read timeout")
    return 0
