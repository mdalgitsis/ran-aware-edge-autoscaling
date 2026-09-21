# Copyright 2026 Nearby Computing S.L.
"""How many users a service migration disrupts, by placement strategy.

One of the two offline studies behind the EuCNC 2025 paper (see
docs/reproducing.md). It measures UASM -- Users Affected by Service Migration,
as a percentage -- when an edge service is relocated under four strategies:

* **Random-SM** -- pick a destination at random.
* **CPU-based-High-SM** / **CPU-based-Low-SM** -- pick by CPU headroom, which
  is what a conventional scheduler does.
* **NASO** -- network-aware, the proposed strategy: pick using what the
  network already knows about where users and their traffic are.

The claim it supports is that CPU-based placement is blind to the thing that
actually determines disruption -- where the traffic is -- and so relocates
services in ways that break more sessions than necessary.

The algorithm below is unchanged from the version used for the paper; only the
driver was reworked to take an output directory and avoid a blocking show().
"""

import argparse
import csv
import pathlib

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np


# Function to generate a more diverse user and traffic distribution
def generate_traffic_distribution(num_users, num_apps):
    # Define user groups with different traffic patterns
    high_traffic_users = int(num_users * 0.1)  # 10% of users with high traffic
    low_traffic_users = num_users - high_traffic_users  # Remaining users with low traffic

    # Assign traffic demands based on user groups
    high_traffic_mbps = np.random.randint(15, 20, size=high_traffic_users)  # High traffic users (15-20 Mbps)
    low_traffic_mbps = np.random.randint(2, 8, size=low_traffic_users)  # Low traffic users (2-8 Mbps)

    # Combine traffic demands
    mbps_per_user = np.concatenate((high_traffic_mbps, low_traffic_mbps))
    np.random.shuffle(mbps_per_user)  # Shuffle to mix high and low traffic users

    # Randomly assign users to each application, ensuring diversity in the number of users per app
    users_per_app = np.random.randint(1, num_users // 2, size=num_apps)
    users_per_app = users_per_app / users_per_app.sum() * num_users  # Normalize to sum to num_users

    # Calculate traffic per app, where some apps may have high users and low traffic or low users and high traffic
    app_traffic = []
    user_idx = 0
    for i in range(num_apps):
        app_user_count = int(users_per_app[i])
        app_traffic.append(sum(mbps_per_user[user_idx:user_idx + app_user_count]))
        user_idx += app_user_count

    return users_per_app, app_traffic


# Function to analyze migration strategies
def analyze_migration_strategies(strategy, num_users, min_replica_mbps, num_iterations=1000):
    # Configuration
    num_apps = 10
    server_capacity = 16  # CPU cores
    min_replica_cpu = 2
    max_replica_cpu = 3
    weight_factor = 1  # High weight factor

    affected_percentages = []

    for _ in range(num_iterations):
        # Generate traffic distribution with random users and traffic per app
        users_per_app, app_traffic = generate_traffic_distribution(num_users, num_apps)

        # Calculate CPU requirements based on the generated traffic
        cpu_requirements = []
        for mbps in app_traffic:
            replicas = int(np.ceil(mbps / min_replica_mbps))
            cpu_per_replica = np.random.randint(min_replica_cpu, max_replica_cpu + 1)
            total_cpu = replicas * cpu_per_replica
            cpu_requirements.append(total_cpu)

        # Migration logic
        apps = list(range(num_apps))  # Application indices
        total_cpu_used = sum(cpu_requirements)
        apps_to_migrate = []

        if total_cpu_used > server_capacity:
            if strategy == "random":
                np.random.shuffle(apps)
            elif strategy == "cpu-based-high-cpu":
                apps.sort(key=lambda i: cpu_requirements[i], reverse=True)  # Highest CPU first
            elif strategy == "cpu-based-low-cpu":
                apps.sort(key=lambda i: cpu_requirements[i])  # Lowest CPU first
            elif strategy == "network-aware":
                apps.sort(key=lambda i: (users_per_app[i], cpu_requirements[i]))  # Fewest users and weighted CPU

            migrated_cpu = 0
            for app in apps:
                if total_cpu_used - migrated_cpu <= server_capacity:
                    break
                migrated_cpu += cpu_requirements[app]
                apps_to_migrate.append(app)

        # Calculate percentage of affected users
        migrated_users = sum([users_per_app[app] for app in apps_to_migrate])
        percentage_affected = (migrated_users / num_users) * 100
        affected_percentages.append(percentage_affected)

    # Return the average percentage over multiple iterations
    return np.mean(affected_percentages)

DEFAULT_USER_COUNTS = [10, 20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 400]
STRATEGIES = ["random", "cpu-based-high-cpu", "cpu-based-low-cpu", "network-aware"]
LABELS = {
    "random": "Random-SM",
    "cpu-based-high-cpu": "CPU-based-High-SM",
    "cpu-based-low-cpu": "CPU-based-Low-SM",
    "network-aware": "NASO",
}
TRAFFIC_SCENARIOS = [100, 500]  # Mbps served by one replica


def run_study(user_counts=None, iterations=1000, seed=42):
    """Return {mbps: {strategy: [UASM% per user count]}}."""
    user_counts = user_counts or DEFAULT_USER_COUNTS
    np.random.seed(seed)

    results = {mbps: {s: [] for s in STRATEGIES} for mbps in TRAFFIC_SCENARIOS}
    for num_users in user_counts:
        for strategy in STRATEGIES:
            for mbps in TRAFFIC_SCENARIOS:
                results[mbps][strategy].append(
                    analyze_migration_strategies(
                        strategy, num_users, min_replica_mbps=mbps,
                        num_iterations=iterations,
                    )
                )
    return results, user_counts


def write_csv(results, user_counts, path):
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["Number of Users", "Strategy", "Traffic Scenario", "Affected Percentage"]
        )
        for index, num_users in enumerate(user_counts):
            for strategy in STRATEGIES:
                for mbps in TRAFFIC_SCENARIOS:
                    writer.writerow(
                        [num_users, strategy, f"{mbps} Mbps",
                         results[mbps][strategy][index]]
                    )


def plot(results, user_counts, path=None, show=False):
    tableau = list(mcolors.TABLEAU_COLORS.values())
    colors = dict(zip(STRATEGIES, [tableau[0], tableau[1], tableau[2], tableau[3]]))

    plt.figure(figsize=(10, 6))
    for strategy in STRATEGIES:
        plt.plot(user_counts, results[100][strategy], marker="o",
                 label=f"100 Mbps - {LABELS[strategy]}", color=colors[strategy])
    for strategy in STRATEGIES:
        plt.plot(user_counts, results[500][strategy], marker="x", linestyle="--",
                 label=f"500 Mbps - {LABELS[strategy]}", color=colors[strategy])

    plt.xlabel("Number of users in a region", fontsize=18)
    plt.ylabel("UASM (%)", fontsize=18)
    plt.xticks(fontsize=16)
    plt.yticks(fontsize=16)
    plt.legend(loc="upper left", fontsize=10)
    plt.ylim(0, 100)
    plt.grid(True)
    plt.tight_layout()
    if path:
        plt.savefig(path)
    if show:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    out = pathlib.Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results, user_counts = run_study(iterations=args.iterations)
    write_csv(results, user_counts, out / "migration_results.csv")
    plot(results, user_counts, out / "users_affected_migration_comparison.pdf",
         show=args.show)

    for strategy in STRATEGIES:
        mean = np.mean(results[100][strategy])
        print(f"{LABELS[strategy]:<20} mean UASM @100Mbps: {mean:5.1f}%")
    print(f"\nWrote migration_results.csv and the figure to {out}/")


if __name__ == "__main__":
    main()
