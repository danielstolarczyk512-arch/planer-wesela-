"""Test obciążeniowy (Locust, MIT): typowe użycie aplikacji przez pary.

Przygotowanie: `task up`, `uv run python -m scripts.seed --load-users 50`.
Uruchomienie: `task load` (domyślnie 50 użytkowników, 2 minuty) albo z interfejsem:
`uv run locust -f loadtest/locustfile.py --host http://127.0.0.1:8010`.

Każdy wirtualny użytkownik loguje się na własne konto, zakłada wesele (z zadaniami
z szablonu), dodaje gości i stoły, a potem przegląda pulpit, listy i plan stołów
i od czasu do czasu coś zapisuje. Proporcje: ok. 85% odczytów, 15% zapisów.
Na koniec usuwa swoje wesele. Pozostałości po przerwanym teście: `scripts.cleanup_loadtest`.
"""

import itertools
import os
import random
import threading

from locust import HttpUser, between, task

PASSWORD = os.environ.get("WP_SEED_PASSWORD", "Demo-Wesele-2027!")  # gitleaks:allow
API = "/api/v1"
_ids = itertools.count()
_lock = threading.Lock()


class Couple(HttpUser):
    wait_time = between(1, 4)  # człowiek klika, nie skrypt

    def on_start(self) -> None:
        with _lock:
            n = next(_ids)
        r = self.client.post(
            f"{API}/auth/login",
            json={"email": f"loadtest-{n % 50}@example.com", "password": PASSWORD},
            name="/auth/login",
        )
        r.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        w = self.client.post(
            f"{API}/weddings",
            json={"name": f"Obciążenie {n}", "planned_month": "2027-09", "ceremony_type": "civil"},
            name="/weddings [POST]",
        ).json()
        self.url = f"{API}/weddings/{w['id']}"
        self.task_ids = [
            t["id"]
            for t in self.client.get(f"{self.url}/tasks", name="/tasks").json()["items"][:20]
        ]
        for i in range(8):
            h = self.client.post(
                f"{self.url}/households",
                json={"name": f"Rodzina {i}", "group_label": random.choice(["praca", "rodzina"])},
                name="/households [POST]",
            ).json()
            for first in ("Anna", "Jan"):
                self.client.post(
                    f"{self.url}/households/{h['id']}/guests",
                    json={"first_name": first},
                    name="/guests [POST]",
                )
        for i in range(3):
            self.client.post(
                f"{self.url}/seating/tables",
                json={"name": f"Stół {i + 1}", "capacity": 8},
                name="/seating/tables [POST]",
            )

    def on_stop(self) -> None:
        # Sprzątanie: wesele testu nie zostaje w bazie (wcześniej zostało ich ponad 300).
        if getattr(self, "url", None):
            self.client.delete(self.url, name="/weddings/{id} [DELETE]")

    @task(6)
    def summary(self) -> None:
        self.client.get(f"{self.url}/summary", name="/summary")

    @task(4)
    def task_list(self) -> None:  # nie „tasks”: to nazwa zarezerwowana przez Locust
        self.client.get(f"{self.url}/tasks", name="/tasks")

    @task(3)
    def guests(self) -> None:
        self.client.get(f"{self.url}/guests", name="/guests")

    @task(3)
    def budget(self) -> None:
        self.client.get(f"{self.url}/budget/overview", name="/budget/overview")

    @task(2)
    def seating(self) -> None:
        self.client.get(f"{self.url}/seating", name="/seating")

    @task(2)
    def complete_task(self) -> None:
        if self.task_ids:
            with self.client.post(
                f"{self.url}/tasks/{random.choice(self.task_ids)}/complete",
                name="/tasks/{id}/complete",
                catch_response=True,
            ) as r:
                if r.status_code == 409:  # już zrobione: poprawna odpowiedź domenowa
                    r.success()

    @task(1)
    def add_task(self) -> None:
        self.client.post(
            f"{self.url}/tasks", json={"title": "Zadanie z testu"}, name="/tasks [POST]"
        )

    @task(1)
    def auto_seating(self) -> None:
        with self.client.post(
            f"{self.url}/seating/auto", json={}, name="/seating/auto", catch_response=True
        ) as r:
            if r.status_code == 429:  # limit 30/h na wesele: oczekiwane zachowanie
                r.success()
