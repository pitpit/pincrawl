import '@tailwindplus/elements';

import './main.css'
import PushNotificationComponent from './PushNotificationComponent';
import LanguageSelectorComponent from './LanguageSelectorComponent';
import EmailNotificationComponent from './EmailNotificationComponent';


document.addEventListener('DOMContentLoaded', async () => {
  new EmailNotificationComponent('emailButton');
  (new PushNotificationComponent('pushButton', 'testPushButton')).mount();
  new LanguageSelectorComponent('language');
});
