import pytest


def test_index(client):
    response = client.get("/client/index.html")
    assert response.status_code == 200


@pytest.fixture(scope="class")
def room_id(client):
    response = client.post("/room")
    assert response.status_code == 200

    room_id: int = int(response.json())
    return room_id


def header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="class")
def user1(client, room_id):
    response = client.post(f"/user/{room_id}", json={"user_name": "user1"})
    assert response.status_code == 200

    return header(response.json())


@pytest.fixture(scope="class")
def user2(client, room_id):
    response = client.post(f"/user/{room_id}", json={"user_name": "user2"})
    assert response.status_code == 200

    return header(response.json())


class TestAddAndDeleteUser:
    def test_add_and_delete_user(self, client, room_id, user1):
        response = client.get(f"/room/{room_id}", headers=user1)
        data = response.json()
        assert len(data["members"]) == 1

        with client.websocket_connect(f"/room-ws/{room_id}", headers=user1) as ws:
            response = client.post(f"/user/{room_id}", json={"user_name": "user3"})
            assert response.status_code == 200
            user3 = header(response.json())

            # when a user is appended, websocket's notication arrives
            ws_received = ws.receive_json()
            assert ws_received["op"] == "add_member"
            assert ws_received["user_name"] == "user3"
            assert "user_id" in ws_received
            user3_id = ws_received["user_id"]

            response = client.get(f"/room/{room_id}", headers=user1)
            data = response.json()
            assert len(data["members"]) == 2

            with client.websocket_connect(f"/room-ws/{room_id}", headers=user3) as _:
                pass

            # the user3 went away
            ws_received = ws.receive_json()
            assert ws_received["op"] == "delete_member"
            assert ws_received["user_id"] == user3_id

            response = client.get(f"/room/{room_id}", headers=user1)
            data = response.json()
            assert len(data["members"]) == 1
