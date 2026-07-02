from signalgrid.connectors.base import Connector
from signalgrid.connectors.domain import DomainConnector
from signalgrid.connectors.github import GitHubConnector
from signalgrid.connectors.greenhouse import GreenhouseConnector
from signalgrid.connectors.hackernews import HackerNewsConnector

ALL_CONNECTORS: list[type[Connector]] = [
    GitHubConnector,
    DomainConnector,
    HackerNewsConnector,
    GreenhouseConnector,
]

__all__ = [
    "Connector",
    "DomainConnector",
    "GitHubConnector",
    "GreenhouseConnector",
    "HackerNewsConnector",
    "ALL_CONNECTORS",
]
