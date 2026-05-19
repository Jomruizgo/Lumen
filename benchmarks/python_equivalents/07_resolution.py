import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TeamNotFoundError(Exception):
    pass

def resolve_team(team_name: str) -> dict:
    teams = _query_org_teams(team_name)
    if len(teams) == 1:
        return teams[0]
    elif len(teams) > 1:
        answer = input(f"¿Cuál equipo? {[t['name'] for t in teams]}: ")
        return next(t for t in teams if answer in t["name"])
    else:
        raise TeamNotFoundError(f"Equipo no encontrado: {team_name}")

def _query_org_teams(name: str) -> list:
    return []  # placeholder for org directory lookup

def send_email(to: str, subject: str, body: str) -> None:
    logger.info(f"Sending email to {to}: {subject}")

def send_to_team(team_name: str, subject: str, body: str) -> None:
    team = resolve_team(team_name)
    for member in team.get("members", []):
        send_email(to=member["email"], subject=subject, body=body)

if __name__ == "__main__":
    send_to_team("engineering", "Reunión mañana", "10am sala 3")
