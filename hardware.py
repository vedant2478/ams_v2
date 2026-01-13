# test_key_status.py
from amscan import AMS_CAN, CAN_LED_STATE_OFF, CAN_LED_STATE_ON
from time import sleep
import sys


class KeyStatusTester:
    def __init__(self):
        print("=" * 60)
        print("KEY STATUS TESTER - Initializing AMS CAN")
        print("=" * 60)
        
        try:
            self.ams_can = AMS_CAN()
            sleep(6)  # Wait for CAN bus initialization
            print(f"\n✓ CAN Bus initialized successfully")
            print(f"✓ Detected {len(self.ams_can.key_lists)} key strip(s)")
        except Exception as e:
            print(f"✗ Error initializing CAN: {e}")
            sys.exit(1)

    def is_key_present(self, strip_id, position):
        """
        Check if a key is present at the given strip and position.
        Returns (present, key_id) tuple.
        """
        key_id = self.ams_can.get_key_id(strip_id, position)
        
        if key_id and key_id != "00000" and key_id != False:
            return True, key_id
        else:
            return False, None

    def check_single_strip(self, strip_id, num_positions=14):
        """
        Check all positions on a single strip.
        Default is 14 positions (1-14).
        """
        print(f"\n{'='*60}")
        print(f"STRIP {strip_id} - Checking {num_positions} positions")
        print(f"{'='*60}")
        
        present_keys = []
        empty_positions = []
        
        for position in range(1, num_positions + 1):
            print(f"Checking position {position:2d}...", end=" ", flush=True)
            
            is_present, key_id = self.is_key_present(strip_id, position)
            
            if is_present:
                print(f"✓ KEY PRESENT - ID: {key_id}")
                present_keys.append({
                    'position': position,
                    'key_id': key_id
                })
            else:
                print(f"✗ Empty")
                empty_positions.append(position)
            
            sleep(0.3)  # Small delay between checks
        
        return present_keys, empty_positions

    def display_summary(self, strip_id, present_keys, empty_positions):
        """Display summary for a strip."""
        total = len(present_keys) + len(empty_positions)
        
        print(f"\n{'─'*60}")
        print(f"STRIP {strip_id} SUMMARY")
        print(f"{'─'*60}")
        print(f"Total positions checked: {total}")
        print(f"Keys present: {len(present_keys)}")
        print(f"Empty positions: {len(empty_positions)}")
        
        if present_keys:
            print(f"\n📌 Keys found at positions:")
            for key in present_keys:
                print(f"   Position {key['position']:2d}: Key ID {key['key_id']}")
        
        if empty_positions:
            print(f"\n⚪ Empty positions: {', '.join(map(str, empty_positions))}")

    def check_all_strips(self, num_positions=14):
        """Check all detected strips."""
        if not self.ams_can.key_lists:
            print("✗ No key strips detected!")
            return
        
        all_results = {}
        
        for strip_id in self.ams_can.key_lists:
            present_keys, empty_positions = self.check_single_strip(
                strip_id, 
                num_positions
            )
            all_results[strip_id] = {
                'present': present_keys,
                'empty': empty_positions
            }
            self.display_summary(strip_id, present_keys, empty_positions)
        
        # Overall summary
        print(f"\n{'='*60}")
        print("OVERALL SUMMARY")
        print(f"{'='*60}")
        
        total_keys = sum(len(r['present']) for r in all_results.values())
        total_empty = sum(len(r['empty']) for r in all_results.values())
        
        print(f"Total strips: {len(self.ams_can.key_lists)}")
        print(f"Total keys present: {total_keys}")
        print(f"Total empty positions: {total_empty}")
        
        return all_results

    def test_with_led_indication(self, strip_id, num_positions=14):
        """
        Test key presence and light up LED for occupied positions.
        Useful for visual verification.
        """
        print(f"\n{'='*60}")
        print(f"LED INDICATION TEST - STRIP {strip_id}")
        print(f"{'='*60}")
        
        # Turn off all LEDs first
        print("Turning off all LEDs...")
        self.ams_can.set_all_LED_OFF(strip_id)
        sleep(1)
        
        present_keys = []
        
        for position in range(1, num_positions + 1):
            is_present, key_id = self.is_key_present(strip_id, position)
            
            if is_present:
                print(f"Position {position:2d}: KEY PRESENT (ID: {key_id}) - LED ON")
                self.ams_can.set_single_LED_state(strip_id, position, CAN_LED_STATE_ON)
                present_keys.append({'position': position, 'key_id': key_id})
            else:
                print(f"Position {position:2d}: Empty")
            
            sleep(0.3)
        
        print(f"\n✓ LED indication complete. {len(present_keys)} keys detected.")
        print("LEDs are ON for positions with keys.")
        
        return present_keys

    def cleanup(self):
        """Clean up resources."""
        print("\nCleaning up...")
        try:
            # Turn off all LEDs
            for strip_id in self.ams_can.key_lists:
                self.ams_can.set_all_LED_OFF(strip_id)
            self.ams_can.cleanup()
            print("✓ Cleanup complete")
        except Exception as e:
            print(f"✗ Error during cleanup: {e}")


def main():
    """Main test function."""
    tester = KeyStatusTester()
    
    try:
        # Option 1: Check all strips (basic check)
        print("\n[TEST 1] Checking all key positions...")
        results = tester.check_all_strips(num_positions=14)
        
        # Option 2: LED indication test (visual verification)
        print("\n\n[TEST 2] LED indication test")
        print("Press Ctrl+C to skip LED test, or wait 3 seconds...")
        sleep(3)
        
        for strip_id in tester.ams_can.key_lists:
            tester.test_with_led_indication(strip_id, num_positions=14)
        
        print("\n\nLEDs will stay on for 10 seconds for visual inspection...")
        sleep(10)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n✗ Error during test: {e}")
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()
