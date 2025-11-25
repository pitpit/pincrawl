import '@tailwindplus/elements';

import './main.css'
import PushNotificationComponent from './PushNotificationComponent';
import LanguageSelectorComponent from './LanguageSelectorComponent';
import EmailNotificationComponent from './EmailNotificationComponent';


const emailNotificationComponent = new EmailNotificationComponent('emailButton');
const pushNotificationComponent = new PushNotificationComponent('pushButton', 'testPushButton');
const languageSelectorComponent = new LanguageSelectorComponent('language');

document.addEventListener('DOMContentLoaded', async () => {
  languageSelectorComponent.mount();
  emailNotificationComponent.mount();
  pushNotificationComponent.mount();
});
