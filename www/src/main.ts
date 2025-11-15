import '@tailwindplus/elements';

import './main.css'
import PushNotificationComponent from './PushNotificationComponent';
import LanguageSelectorComponent from './LanguageSelectorComponent';
import EmailNotificationComponent from './EmailNotificationComponent';


document.addEventListener('DOMContentLoaded', () => {
  new EmailNotificationComponent('emailButton');
  new PushNotificationComponent((window as any).OneSignal, 'pushButton', 'testPushButton');
  new LanguageSelectorComponent('language');
});
