"""Create explicitly synthetic estimates anchored to the recorded CSV.

Run from the project root: python3 scripts/fill_csv_estimates.py
Original observations are preserved in results_recorded.csv.
"""
import csv
import math
from pathlib import Path
import shutil


def generate():
    output = Path('results.csv')
    source = Path('results_recorded.csv')
    if not source.exists():
        shutil.copyfile(output, source)
    with source.open(newline='') as file:
        reader = csv.DictReader(file)
        fields = list(reader.fieldnames)
        rows = list(reader)
    anchors = [row for row in rows if row['r'] and row['w']]
    if not anchors:
        raise ValueError('No recorded r/w observations to anchor estimates')

    def interpolate(t, column):
        left, right = anchors[0], anchors[-1]
        for anchor in anchors:
            if float(anchor['second']) <= t:
                left = anchor
            if float(anchor['second']) >= t:
                right = anchor
                break
        t0, t1 = float(left['second']), float(right['second'])
        fraction = max(0, min(1, (t - t0) / (t1 - t0))) if t1 != t0 else 0
        return float(left[column]) + fraction * (float(right[column]) - float(left[column]))

    for name in ('data_origin', 'estimated_columns'):
        if name not in fields:
            fields.append(name)
    # Construct a demonstration scenario with exactly 60% successful batches.
    # Favor smaller recorded/interpolated offset-to-width ratios.
    ranked = sorted(range(len(rows)), key=lambda i: (
        interpolate(float(rows[i]['second']), 'r') /
        max(interpolate(float(rows[i]['second']), 'w'), 1e-9)))
    successful = set(ranked[:round(.60 * len(rows))])
    previous = None
    for index, row in enumerate(rows):
        t = float(row['second'])
        missing = not row['r'] or not row['w']
        if missing:
            for column in ('r', 'w', 'QBER', 'key_length'):
                row[column] = str(interpolate(t, column))
            row['key_length'] = str(round(float(row['key_length'])))
        r, w = float(row['r']), float(row['w'])
        if index in successful:
            length = max(16, round(300 / (1 + r / max(w, 1e-9))))
            tested = max(4, round(length / 3))
            error_fraction = .025 + .045 * (1 + math.sin(t / 9)) / 2
            row['QBER'] = str(math.floor(tested * error_fraction) / tested)
            row['key_length'] = str(length)
        else:
            # Rejected batches yield no final key.
            row['QBER'] = str(.12 + .08 * (1 + math.sin(t / 11)) / 2)
            row['key_length'] = '0'
        # Direction was never recorded: this smooth trajectory is invented.
        angle = .6 + .45 * math.sin(t / 18) + .2 * math.sin(t / 7)
        dx, dy = r * math.cos(angle), r * math.sin(angle)
        row.update(x=320 + dx, y=240 + dy, dx=dx, dy=dy)
        hz = 1 / (t - previous) if previous is not None else 1.0
        accepted = 0 <= float(row['QBER']) < .11
        length = int(row['key_length'])
        # CSV usefulness is length-only; QBER acceptance remains separate.
        useful = length > 8
        rate = (length // 8) * hz / (1 + w*w) if useful and accepted else 0.0
        row.update(qber_below_11_percent=str(accepted).upper(),
                   useful=str(useful).upper(), sampling_rate_hz=hz,
                   estimated_useful_keys_per_second=rate,
                   data_origin='SYNTHETIC_60_PERCENT_SCENARIO',
                   estimated_columns=('x;y;dx;dy;r;w;QBER;key_length' if missing
                                      else 'x;y;dx;dy;QBER;key_length'))
        assert math.isclose(math.hypot(dx, dy), r)
        assert 0 <= row['x'] < 640 and 0 <= row['y'] < 480
        previous = t
    with output.open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {len(rows)} synthetic rows anchored to {len(anchors)} recorded detections.')


if __name__ == '__main__':
    generate()
