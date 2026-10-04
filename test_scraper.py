import json
import sys
from scraper import get_all_matches
from filter import get_match_state, is_pakistan_match

def run_test():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("🏏 Fetching data from Cricbuzz... (This takes a few seconds)")
    all_data = get_all_matches()

    print("\n" + "="*50)
    print(" RAW SCRAPER OUTPUT (Pakistan / PSL Matches Only)")
    print("="*50)
    
    # Check all pools for Pakistan matches to see what the scraper actually grabbed
    for pool_name in ['live', 'upcoming', 'recent']:
        for m in all_data.get(pool_name, []):
            if is_pakistan_match(m):
                print(f"\nPool: [{pool_name.upper()}]")
                print(json.dumps(m, indent=2))

    print("\n" + "="*50)
    print(" FILTER.PY FINAL DECISION")
    print("="*50)
    
    state, matches = get_match_state(all_data)
    print(f"STATE DETERMINED: '{state}'")
    
    if matches:
        print("MATCH TO DISPLAY:")
        print(json.dumps(matches[0], indent=2))
    else:
        print("MATCH TO DISPLAY: None")
    if all_data.get("errors"):
        print("REFRESH ERRORS:", json.dumps(all_data["errors"], indent=2))
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(run_test())
