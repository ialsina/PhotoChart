from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase

from photograph.models import Photograph, PhotoPath
from photochart.protocols import calculate_checksum

from .models import PlannedAction
from .serializers import PlannedActionSerializer
from .tasks import execute_planned_action


class PlannedActionTests(TestCase):
    def test_delete_requires_a_photograph(self):
        serializer = PlannedActionSerializer(
            data={"action_type": PlannedAction.ActionType.DELETE}
        )

        assert not serializer.is_valid()

    def test_creation_enqueues_action_for_operator(self):
        photograph = Photograph.objects.create()
        user = User.objects.create_user("operator", password="secret")
        user.user_permissions.add(Permission.objects.get(codename="operate_organizer"))
        self.client.login(username="operator", password="secret")

        with patch("planner.views.execute_planned_action.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    "/api/planned-actions/",
                    {
                        "action_type": PlannedAction.ActionType.DELETE,
                        "photograph": photograph.pk,
                    },
                )

        assert response.status_code == 201
        delay.assert_called_once_with(response.json()["id"])

    def test_delete_verifies_file_and_preserves_audit(self):
        path = self._temp_photo()
        photograph = Photograph.objects.create(checksum=calculate_checksum(str(path)))
        PhotoPath.objects.create(
            photograph=photograph,
            path=str(path),
            filename=path.name,
            device="test",
        )
        action = PlannedAction.objects.create(
            action_type=PlannedAction.ActionType.DELETE,
            photograph=photograph,
        )

        status = execute_planned_action(action.pk)

        action.refresh_from_db()
        assert status == PlannedAction.Status.COMPLETED
        assert action.photograph is None
        assert not path.exists()

    def _temp_photo(self):
        from pathlib import Path
        from tempfile import mkstemp
        import os

        descriptor, name = mkstemp(suffix=".jpg")
        os.close(descriptor)
        path = Path(name)
        path.write_bytes(b"photo")
        self.addCleanup(path.unlink, missing_ok=True)
        return path
