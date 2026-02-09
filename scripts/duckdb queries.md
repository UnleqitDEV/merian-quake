## Updates per frame
select last_update_count AS update_count, COUNT(*) AS count, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percent from read_json("C:\Users\utqns\Documents\Bachelorarbeit\codebase\merian-quake\build\mc_dump.json") where last_update_count > 0 group by last_update_count order by last_update_count;

┌──────────────┬────────┬─────────┐
│ update_count │ count  │ percent │
│    int64     │ int64  │ double  │
├──────────────┼────────┼─────────┤
│            1 │ 224230 │   37.52 │
│            2 │ 136511 │   22.84 │
│            3 │  87234 │    14.6 │
│            4 │  54621 │    9.14 │
│            5 │  34581 │    5.79 │
│            6 │  21634 │    3.62 │
│            7 │  13423 │    2.25 │
│            8 │   8618 │    1.44 │
│            9 │   5670 │    0.95 │
│           10 │   3655 │    0.61 │
│           11 │   2415 │     0.4 │
│           12 │   1653 │    0.28 │
│           13 │   1054 │    0.18 │
│           14 │    666 │    0.11 │
│           15 │    524 │    0.09 │
│           16 │    375 │    0.06 │
│           17 │    235 │    0.04 │
│           18 │    165 │    0.03 │
│           19 │    114 │    0.02 │
│           20 │     59 │    0.01 │
│           21 │     41 │    0.01 │
│           22 │     25 │     0.0 │
│           23 │     21 │     0.0 │
│           24 │      9 │     0.0 │
│           25 │     15 │     0.0 │
│           26 │      6 │     0.0 │
│           27 │      7 │     0.0 │
│           28 │      9 │     0.0 │
│           29 │      8 │     0.0 │
│           30 │      3 │     0.0 │
│           31 │      2 │     0.0 │
│           32 │      1 │     0.0 │
├──────────────┴────────┴─────────┤
│ 32 rows               3 columns │
└─────────────────────────────────┘

## Updates succeeded vs cancelled
SELECT status, total, ROUND(total * 100.0 / SUM(total) OVER (), 2) AS percentage FROM (SELECT 'succeeded' AS status, SUM(update_succeeded) AS total FROM read_json("C:\Users\utqns\Documents\Bachelorarbeit\codebase\merian-quake\build\mc_dump.json") WHERE (update_canceled + update_succeeded) > 0 UNION ALL SELECT 'canceled' AS status, SUM(update_canceled) AS total FROM read_json("C:\Users\utqns\Documents\Bachelorarbeit\codebase\merian-quake\build\mc_dump.json") WHERE (update_canceled + update_succeeded) > 0);

### 1. Run
┌───────────┬────────────┬────────────┐
│  status   │   total    │ percentage │
│  varchar  │   int128   │   double   │
├───────────┼────────────┼────────────┤
│ succeeded │ 6243224079 │      89.14 │
│ canceled  │  760661973 │      10.86 │
└───────────┴────────────┴────────────┘

### 2. Run
┌───────────┬────────────┬────────────┐
│  status   │   total    │ percentage │
│  varchar  │   int128   │   double   │
├───────────┼────────────┼────────────┤
│ succeeded │ 4654721875 │      89.33 │
│ canceled  │  555901336 │      10.67 │
└───────────┴────────────┴────────────┘