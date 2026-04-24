import json

with open(r'C:\Users\durel\Desktop\D_M_R_E\backend\DMRE_Reranker_Training.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i, cell in enumerate(nb.get('cells', [])):
    if cell.get('cell_type') in ['code', 'markdown']:
        print(f"\n--- Cell {i} ({cell.get('cell_type')}) ---")
        print("".join(cell.get('source', [])))
        if cell.get('cell_type') == 'code':
            for out in cell.get('outputs', []):
                if 'text' in out:
                    text_out = "".join(out['text'])
                    if 'F1' in text_out or 'score' in text_out or 'Score' in text_out:
                        print(f"OUTPUT CONTAINS SCORE: {text_out.strip()}")
