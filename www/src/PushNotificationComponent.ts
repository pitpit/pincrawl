
import States from './States';

class PushNotificationComponent {

    pushButton: HTMLButtonElement | null = null;
    testPushButton: HTMLButtonElement | null = null;
    OneSignal: any;
    pushButtonStates: States;
    testPushButtonStates: States;

    constructor(OneSignal: any, pushButtonId: string, testPushButtonId: string) {
        this.OneSignal = OneSignal;
        this.pushButton = document.getElementById(pushButtonId) as HTMLButtonElement | null;
        this.testPushButton = document.getElementById(testPushButtonId) as HTMLButtonElement | null;
        this.pushButtonStates = new States(this.pushButton);
        this.testPushButtonStates = new States(this.testPushButton);

        this.refreshUI();

        if (this.pushButton) {
            this.pushButton.addEventListener('click', async () => {
                if (!this.OneSignal) {
                    console.error('OneSignal is not initialized.');
                }
                try {
                    const optedIn = await this.OneSignal.User.PushSubscription.optedIn;
                    if (optedIn) {
                        await this.OneSignal.User.PushSubscription.optOut();
                    } else {
                        await this.OneSignal.User.PushSubscription.optIn();
                    }
                } catch (error) {
                    console.error('Error toggling push subscription:', error);
                } finally {
                    await this.refreshUI();
                }
            });
        }

        if (this.testPushButton) {

            this.testPushButton.addEventListener('click', async () => {
                var previousState = this.testPushButtonStates.getCurrent();
                this.testPushButtonStates.change('sending');

                try {
                    const response = await fetch('/api/test-push-notification', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        }
                    });

                    if (response.ok) {
                        this.testPushButtonStates.change('sent');
                    } else {
                        throw new Error('Failed to send test push notification');
                    }
                } catch (error) {
                    this.testPushButtonStates.change('error');
                } finally {
                    setTimeout(() => {
                        this.testPushButtonStates.change(previousState);
                    }, 2000);
                }
            });
        };
    }

    async refreshUI() {
        const optedIn = await this.OneSignal?.User.PushSubscription.optedIn;
        if (optedIn) {
            this.pushButtonStates.change('subscribed');
            this.testPushButtonStates.change('enabled');
        } else {
            this.pushButtonStates.change('unsubscribed');
            this.testPushButtonStates.change('disabled');
        }
    }
}

export default PushNotificationComponent;