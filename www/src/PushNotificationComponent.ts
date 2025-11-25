
import States from './States';

class PushNotificationComponent {

    pushButton: HTMLButtonElement | null = null;
    testPushButton: HTMLButtonElement | null = null;
    pushButtonStates: States;
    testPushButtonStates: States;

    constructor(pushButtonId: string, testPushButtonId: string) {
        this.pushButton = document.getElementById(pushButtonId) as HTMLButtonElement | null;
        this.testPushButton = document.getElementById(testPushButtonId) as HTMLButtonElement | null;
        this.pushButtonStates = new States(this.pushButton);
        this.testPushButtonStates = new States(this.testPushButton);

        this.pushButtonStates.change('disabled');
        this.testPushButtonStates.change('disabled');

        // Wait for OneSignal to be ready

        // const isSupported = OneSignal.Notifications && OneSignal.Notifications.isPushSupported();
        // if (!isSupported) {
        //     this.pushButtonStates.change('disabled');
        //     this.testPushButtonStates.change('disabled');
        //     const pushNotSupportedHint = document.getElementById('pushNotSupportedHint');
        //     if (pushNotSupportedHint) {
        //         pushNotSupportedHint.classList.remove('hidden');
        //     }
        //     return;
        // }


    }

    async mount() {
        await this.waitForOneSignal();

        await this.refreshUI();

        if (this.pushButton) {
            this.pushButton.addEventListener('click', async () => {
                this.pushButtonStates.change('loading');
                try {
                    const optedIn = OneSignal.User.PushSubscription.optedIn;
                    if (optedIn) {
                        await OneSignal.User.PushSubscription.optOut();
                    } else {
                        await OneSignal.User.PushSubscription.optIn();
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
                    }, 1000);
                }
            });
        };
    }

    private waitForOneSignal(): Promise<void> {
        return new Promise((resolve) => {
            if (typeof OneSignal !== 'undefined') {
                resolve();
            } else {
                window.OneSignalDeferred = window.OneSignalDeferred || [];
                window.OneSignalDeferred.push(() => {
                    resolve();
                });
            }
        });
    }

    private async refreshUI() {
        const optedIn = OneSignal.User.PushSubscription.optedIn;
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