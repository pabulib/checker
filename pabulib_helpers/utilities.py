from collections import defaultdict


def get_str_with_sep_from(number):
    return f"{number:,d}".replace(",", " ")


def count_votes_per_project(votes):
    counted_votes = defaultdict(int)
    for _, vote in votes.items():
        # Vote strength, if not defined 1 is default
        vote_strength = vote.get("vote_strength", 1)
        projects = vote["vote"].split(",")
        for project in projects:
            counted_votes[project] += vote_strength
    return counted_votes


def create_points_based_on_vote_length(projects):
    points = []
    point = len(projects)
    for _ in projects:
        points.append(point)
        point -= 1
    return points


def count_points_per_project(votes):
    counted_scores = defaultdict(int)
    for _, vote in votes.items():
        # Vote strength, if not defined 1 is default
        projects = vote["vote"].split(",")
        try:
            points = vote["points"].split(",")
        except KeyError:
            points = create_points_based_on_vote_length(projects)
        for project, point in zip(projects, points):
            counted_scores[project] += int(point)
    return counted_scores


def sort_projects_by_results(projects):
    first_project_dict = next(iter(projects.values()))
    if "score" in first_project_dict:
        score_field = "score"
    elif "votes" in first_project_dict:
        score_field = "votes"
    else:
        # If neither score nor votes field exists, return projects unsorted
        return projects

    projects = dict(
        sorted(
            projects.items(),
            key=lambda x: int(x[1][score_field]) if x[1][score_field] else 0,
            reverse=True,
        )
    )
    return projects


def make_cost_printable(cost):
    cost = float(cost)
    return str("{:.2f}".format(cost) if cost % 1 else int(cost))
