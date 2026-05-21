// Curated starter prompts for the DP Practice page.
//
// Each entry maps a pattern (matching a backend SCENE_REGISTRY key) to a
// canonical example: scene + params + reference starter code for both
// Python and C++. The catalog is intentionally small and hand-tuned so
// every card animates cleanly and runs in well under the render budget.
//
// To add a new entry: pick one of the six pattern keys, write the
// example, run the test in backend/tests/test_dp_practice_data.py to
// confirm the scene name still exists.

export type DPPattern =
  | "knapsack_01"
  | "lcs"
  | "edit_distance"
  | "coin_change_2d"
  | "lis"
  | "dp_progression";

export interface DPPracticeProblem {
  pattern: DPPattern;
  title: string;
  description: string;
  steps: { scene: string; params: Record<string, any> }[];
  starterCode: { python: string; cpp: string };
  topicId: string;
}

const KNAPSACK_PY = `def knapsack(items, capacity):
    """items: list of (weight, value). Returns max value."""
    n = len(items)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        w_i, v_i = items[i - 1]
        for w in range(capacity + 1):
            dp[i][w] = dp[i - 1][w]
            if w_i <= w:
                dp[i][w] = max(dp[i][w], dp[i - 1][w - w_i] + v_i)
    return dp[n][capacity]`;

const KNAPSACK_CPP = `int knapsack(vector<pair<int,int>>& items, int cap) {
    int n = items.size();
    vector<vector<int>> dp(n + 1, vector<int>(cap + 1, 0));
    for (int i = 1; i <= n; ++i) {
        int wi = items[i-1].first, vi = items[i-1].second;
        for (int w = 0; w <= cap; ++w) {
            dp[i][w] = dp[i-1][w];
            if (wi <= w) dp[i][w] = max(dp[i][w], dp[i-1][w-wi] + vi);
        }
    }
    return dp[n][cap];
}`;

const LCS_PY = `def lcs(s1, s2):
    n, m = len(s1), len(s2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[n][m]`;

const LCS_CPP = `int lcs(string s1, string s2) {
    int n = s1.size(), m = s2.size();
    vector<vector<int>> dp(n + 1, vector<int>(m + 1, 0));
    for (int i = 1; i <= n; ++i)
        for (int j = 1; j <= m; ++j)
            if (s1[i-1] == s2[j-1]) dp[i][j] = dp[i-1][j-1] + 1;
            else dp[i][j] = max(dp[i-1][j], dp[i][j-1]);
    return dp[n][m];
}`;

const EDIT_DIST_PY = `def edit_distance(s1, s2):
    n, m = len(s1), len(s2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): dp[i][0] = i
    for j in range(m + 1): dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j],     # delete
                                   dp[i][j-1],     # insert
                                   dp[i-1][j-1])   # replace
    return dp[n][m]`;

const EDIT_DIST_CPP = `int editDistance(string s1, string s2) {
    int n = s1.size(), m = s2.size();
    vector<vector<int>> dp(n + 1, vector<int>(m + 1, 0));
    for (int i = 0; i <= n; ++i) dp[i][0] = i;
    for (int j = 0; j <= m; ++j) dp[0][j] = j;
    for (int i = 1; i <= n; ++i)
        for (int j = 1; j <= m; ++j)
            if (s1[i-1] == s2[j-1]) dp[i][j] = dp[i-1][j-1];
            else dp[i][j] = 1 + min({dp[i-1][j], dp[i][j-1], dp[i-1][j-1]});
    return dp[n][m];
}`;

const COIN_CHANGE_PY = `def coin_change_ways(coins, amount):
    n = len(coins)
    dp = [[0] * (amount + 1) for _ in range(n + 1)]
    for i in range(n + 1): dp[i][0] = 1
    for i in range(1, n + 1):
        for w in range(amount + 1):
            dp[i][w] = dp[i - 1][w]
            if w >= coins[i - 1]:
                dp[i][w] += dp[i][w - coins[i - 1]]
    return dp[n][amount]`;

const COIN_CHANGE_CPP = `int coinChangeWays(vector<int>& coins, int amount) {
    int n = coins.size();
    vector<vector<long long>> dp(n + 1, vector<long long>(amount + 1, 0));
    for (int i = 0; i <= n; ++i) dp[i][0] = 1;
    for (int i = 1; i <= n; ++i)
        for (int w = 0; w <= amount; ++w) {
            dp[i][w] = dp[i-1][w];
            if (w >= coins[i-1]) dp[i][w] += dp[i][w - coins[i-1]];
        }
    return dp[n][amount];
}`;

const LIS_PY = `def lis(nums):
    n = len(nums)
    dp = [1] * n
    for i in range(1, n):
        for j in range(i):
            if nums[j] < nums[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)`;

const LIS_CPP = `int lis(vector<int>& nums) {
    int n = nums.size();
    vector<int> dp(n, 1);
    for (int i = 1; i < n; ++i)
        for (int j = 0; j < i; ++j)
            if (nums[j] < nums[i]) dp[i] = max(dp[i], dp[j] + 1);
    return *max_element(dp.begin(), dp.end());
}`;

const FIB_PY = `def fib(n):
    if n < 2: return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b`;

const FIB_CPP = `int fib(int n) {
    if (n < 2) return n;
    int a = 0, b = 1;
    for (int i = 2; i <= n; ++i) { int c = a + b; a = b; b = c; }
    return b;
}`;

export const DP_PRACTICE_PROBLEMS: DPPracticeProblem[] = [
  // ── Knapsack 0/1 ─────────────────────────────────────────────────────
  {
    pattern: "knapsack_01",
    title: "0/1 Knapsack — 3 items, capacity 5",
    description: "Pick a subset of items to maximize value under a weight cap. Recurrence: dp[i][w] = max(dp[i-1][w], dp[i-1][w-wi] + vi).",
    steps: [{
      scene: "knapsack_01",
      params: {
        items: [{ weight: 2, value: 3 }, { weight: 3, value: 4 }, { weight: 4, value: 5 }],
        capacity: 5,
      },
    }],
    starterCode: { python: KNAPSACK_PY, cpp: KNAPSACK_CPP },
    topicId: "knapsack_01",
  },
  {
    pattern: "knapsack_01",
    title: "0/1 Knapsack — 4 items, capacity 7",
    description: "Slightly bigger table — watch the rightmost columns where the heavier items become viable.",
    steps: [{
      scene: "knapsack_01",
      params: {
        items: [{ weight: 1, value: 1 }, { weight: 3, value: 4 }, { weight: 4, value: 5 }, { weight: 5, value: 7 }],
        capacity: 7,
      },
    }],
    starterCode: { python: KNAPSACK_PY, cpp: KNAPSACK_CPP },
    topicId: "knapsack_01",
  },

  // ── Longest Common Subsequence ───────────────────────────────────────
  {
    pattern: "lcs",
    title: "LCS — 'AGCAT' vs 'GAC'",
    description: "Find the longest subsequence present in both strings. Diagonal arrow = match; max-of-neighbors = miss.",
    steps: [{ scene: "lcs", params: { s1: "AGCAT", s2: "GAC" } }],
    starterCode: { python: LCS_PY, cpp: LCS_CPP },
    topicId: "lcs",
  },
  {
    pattern: "lcs",
    title: "LCS — 'ABCBDAB' vs 'BDCAB'",
    description: "A classic textbook example. LCS length is 4 (BCAB or BDAB).",
    steps: [{ scene: "lcs", params: { s1: "ABCBDAB", s2: "BDCAB" } }],
    starterCode: { python: LCS_PY, cpp: LCS_CPP },
    topicId: "lcs",
  },

  // ── Edit Distance ────────────────────────────────────────────────────
  {
    pattern: "edit_distance",
    title: "Edit Distance — 'cat' → 'bat'",
    description: "Minimum insertions/deletions/replacements to transform one string into another. Single-replace expected.",
    steps: [{ scene: "edit_distance", params: { s1: "cat", s2: "bat" } }],
    starterCode: { python: EDIT_DIST_PY, cpp: EDIT_DIST_CPP },
    topicId: "edit_distance",
  },
  {
    pattern: "edit_distance",
    title: "Edit Distance — 'kitten' → 'sit'",
    description: "Different lengths force both replacements and deletions. Watch the three-way min.",
    steps: [{ scene: "edit_distance", params: { s1: "kitten", s2: "sit" } }],
    starterCode: { python: EDIT_DIST_PY, cpp: EDIT_DIST_CPP },
    topicId: "edit_distance",
  },

  // ── Coin Change 2D ───────────────────────────────────────────────────
  {
    pattern: "coin_change_2d",
    title: "Coin Change — coins=[1,2,5], amount=5",
    description: "Number of ways to make an amount. Up arrow = skip coin, left arrow = use coin (rolls capacity).",
    steps: [{ scene: "coin_change_2d", params: { coins: [1, 2, 5], amount: 5 } }],
    starterCode: { python: COIN_CHANGE_PY, cpp: COIN_CHANGE_CPP },
    topicId: "coin_change_2d",
  },
  {
    pattern: "coin_change_2d",
    title: "Coin Change — coins=[2,3,7], amount=8",
    description: "Asymmetric denominations. Some amounts have only one way to make.",
    steps: [{ scene: "coin_change_2d", params: { coins: [2, 3, 7], amount: 8 } }],
    starterCode: { python: COIN_CHANGE_PY, cpp: COIN_CHANGE_CPP },
    topicId: "coin_change_2d",
  },

  // ── LIS ──────────────────────────────────────────────────────────────
  {
    pattern: "lis",
    title: "LIS — [3, 1, 4, 1, 5, 9, 2, 6]",
    description: "Longest strictly-increasing subsequence. For each i, scan all j < i with nums[j] < nums[i].",
    steps: [{ scene: "lis", params: { nums: [3, 1, 4, 1, 5, 9, 2, 6] } }],
    starterCode: { python: LIS_PY, cpp: LIS_CPP },
    topicId: "lis",
  },
  {
    pattern: "lis",
    title: "LIS — [10, 9, 2, 5, 3, 7, 101, 18]",
    description: "LeetCode 300 canonical input. Answer is 4 (2, 3, 7, 101).",
    steps: [{ scene: "lis", params: { nums: [10, 9, 2, 5, 3, 7] } }],
    starterCode: { python: LIS_PY, cpp: LIS_CPP },
    topicId: "lis",
  },

  // ── DP Progression triptych ──────────────────────────────────────────
  {
    pattern: "dp_progression",
    title: "Why DP — Fibonacci",
    description: "Same problem in three forms: naive recursion (exponential) → memoized recursion → bottom-up tabulation.",
    steps: [{ scene: "dp_progression", params: { problem: "fibonacci", n: 5 } }],
    starterCode: { python: FIB_PY, cpp: FIB_CPP },
    topicId: "dp_progression",
  },
];
