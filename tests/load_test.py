from locust import HttpUser, task

class GovernanceUser(HttpUser):

    @task
    def home(self):
        self.client.get("/")
