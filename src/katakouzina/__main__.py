import argparse
import logging
from pathlib import Path
from .app import GraphBrowser
from .config import load_config, read_settings

def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Browse episode graphs')
    parser.add_argument('--data-path', '--data-dir', dest='data_path', type=Path)
    args = parser.parse_args()
    (root/'logs').mkdir(exist_ok=True)
    logging.basicConfig(filename=root/'logs'/'app.log', encoding='utf-8', level=logging.INFO)
    preferences=read_settings(root)
    data_path=args.data_path.resolve() if args.data_path else load_config(root)
    app = GraphBrowser(data_path,preferences,root)
    if preferences["start_maximized"]:app.state("zoomed")
    app.mainloop()

if __name__ == '__main__':
    main()
