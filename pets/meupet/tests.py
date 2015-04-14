import shutil
import tempfile

from django.conf import settings
from django.test import TestCase

from meupet.models import Pet, Kind, Photo
from users.models import OwnerProfile


def get_test_image_file(filename='test.png'):
    from six import BytesIO
    from PIL import Image
    from django.core.files.images import ImageFile

    f = BytesIO()
    image = Image.new('RGB', (200, 200), 'white')
    image.save(f, 'PNG')
    return ImageFile(f, name=filename)


class MeuPetTest(TestCase):
    def setUp(self):
        self._original_media_root = settings.MEDIA_ROOT
        self._temp_media = tempfile.mkdtemp()
        settings.MEDIA_ROOT = self._temp_media
        OwnerProfile.objects.create_user(username='admin', password='admin')

    def tearDown(self):
        shutil.rmtree(self._temp_media, ignore_errors=True)
        settings.MEDIA_ROOT = self._original_media_root

    def create_pet(self, kind, name='Pet', status=Pet.MISSING):
        image = get_test_image_file()
        user = OwnerProfile.objects.first()
        kind = Kind.objects.get_or_create(kind=kind)[0]
        return Pet.objects.create(name='Testing ' + name, description='Bla',
                                  profile_picture=image, owner=user, kind=kind,
                                  status=status)

    def test_display_all_pets(self):
        self.create_pet('Goat', 'Goat')
        self.create_pet('Cat', 'Cat')

        home = self.client.get('/')

        self.assertContains(home, 'Testing Goat')
        self.assertContains(home, 'Testing Cat')

    def test_display_kinds_sidebar(self):
        self.create_pet('Goat')
        self.create_pet('Cat')

        home = self.client.get('/')

        self.assertContains(home, 'Goat')
        self.assertContains(home, 'Cat')

    def test_display_only_pets_from_kind(self):
        self.create_pet('Goat', 'Goat')
        self.create_pet('Cat', 'Cat')
        self.create_pet('Cat', 'Costela')
        kind = Kind.objects.get(kind='Cat')

        content = self.client.get('/lost/{}/'.format(kind.id))
        pets_count = Pet.objects.filter(kind=kind).count()

        self.assertContains(content, 'Testing Cat')
        self.assertContains(content, 'Testing Costela')
        self.assertNotContains(content, 'Testing Goat')
        self.assertEqual(2, pets_count)

    def test_show_edit_button_for_own_if_logged_pet(self):
        self.create_pet('Own Pet')
        self.client.login(username='admin', password='admin')

        response = self.client.get('/pet/1/')

        self.assertContains(response, 'Editar')
        self.assertContains(response, '/pet/1/edit/')

    def test_load_data_for_editing_pet(self):
        self.create_pet('Own Pet', 'Own Pet')
        self.client.login(username='admin', password='admin')

        response = self.client.get('/pet/1/edit/')

        self.assertTemplateUsed(response, 'meupet/edit.html')
        self.assertContains(response, 'Testing Own Pet')
        self.assertContains(response, 'Bla')
        self.assertContains(response, 'Gravar Alterações')

    def test_can_edit_pet(self):
        self.create_pet('Own Pet')
        self.client.login(username='admin', password='admin')
        url = Pet.objects.first().profile_picture.url

        response_post = self.client.post('/pet/1/edit/', data={'name': 'Testing Fuzzy Boots',
                                                               'description': 'My lovely cat',
                                                               'kind': '1',
                                                               'profile_picture': url})
        response_get = self.client.get('/pet/1/')

        self.assertRedirects(response_post, '/pet/1/')
        self.assertContains(response_get, 'Testing Fuzzy Boots')

    def test_show_facebook_only_if_registered(self):
        self.create_pet('Own Pet', 'Own Pet')
        self.create_pet('Second Pet', 'Second Pet')
        user = OwnerProfile.objects.create_user(username='second_user', password='admin')
        user.facebook = 'http://www.facebook.com/owner_profile'
        user.save()
        pet = Pet.objects.first()
        pet.owner = user
        pet.save()

        resp_with_facebook = self.client.get('/pet/1/')

        self.assertContains(resp_with_facebook, 'http://www.facebook.com/owner_profile')

    def test_show_link_for_owner_profile(self):
        self.create_pet('Pet')

        response = self.client.get('/pet/1/')

        self.assertContains(response, '/user/profile/1/')

    def test_should_redirect_if_not_confirmed(self):
        self.client.login(username='admin', password='admin')

        response_lost = self.client.get('/pet/lost/')
        response_adoption = self.client.get('/pet/adoption/')

        self.assertRedirects(response_lost, '/user/profile/edit/')
        self.assertRedirects(response_adoption, '/user/profile/edit/')

    def test_should_access_if_confirmed(self):
        admin = OwnerProfile.objects.first()
        admin.is_information_confirmed = True
        admin.save()
        self.client.login(username='admin', password='admin')

        response_lost = self.client.get('/pet/lost/')
        response_adoption = self.client.get('/pet/adoption/')

        self.assertTemplateUsed(response_lost, 'meupet/register_pet.html')
        self.assertTemplateUsed(response_adoption, 'meupet/register_pet.html')

    def test_only_owner_can_see_edit_page(self):
        OwnerProfile.objects.create_user(username='Other User', password='otherpass')
        self.create_pet('Own Pet')
        self.client.login(username='Other User', password='otherpass')

        response = self.client.get('/pet/1/edit/')

        self.assertRedirects(response, '/pet/1/')

    def test_manager_lost_found(self):
        missing_pet = self.create_pet('Test')
        self.create_pet('Test')
        self.create_pet('Test', status=Pet.FOUND)
        self.create_pet('Test', status=Pet.FOR_ADOPTION)

        pets = Pet.objects.get_lost_or_found(missing_pet.kind.id)

        self.assertEquals(len(pets), 3)

    def test_manager_adoption_adopted(self):
        adopted_pet = self.create_pet('Test', status=Pet.ADOPTED)
        self.create_pet('Test')
        self.create_pet('Test', status=Pet.FOUND)
        self.create_pet('Test', status=Pet.FOR_ADOPTION)

        pets = Pet.objects.get_for_adoption_adopted(adopted_pet.kind.id)

        self.assertEquals(len(pets), 2)

    def test_incorrect_form_submission_reload_page_with_values(self):
        self.client.login(username='admin', password='admin')

        response = self.client.post('/pet/lost/', {'description': 'Test Description'}, follow=True)

        self.assertContains(response, 'Test Description')

    def test_show_add_photo_button_in_pet_page_owner_logged_in(self):
        self.create_pet('Cat')
        self.client.login(username='admin', password='admin')

        response = self.client.get('/pet/1/')

        self.assertContains(response, 'Adicionar Foto')
        self.assertContains(response, 'another_picture')

    def test_show_more_photos_in_pet_detail(self):
        photo = Photo(image=get_test_image_file())
        pet = self.create_pet('Cat')
        pet.photo_set.add(photo)
        pet.save()

        response = self.client.get('/pet/1/')

        self.assertContains(response, 'Outras fotos')