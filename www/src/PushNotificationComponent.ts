
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
                        await this.unsubscribe();
                    } else {
                        await this.subscribe();
                    }
                } catch (error) {
                    console.error('Error toggling push subscription:', error);
                } finally {
                    await this.refreshUI();
                }
            });
        }
    }

    async subscribe() {
        await this.OneSignal.User.PushSubscription.optIn();

        // const response = await fetch('{{ "/api/my-account" }}', {
        //     method: 'PUT',
        //     headers: {
        //         'Content-Type': 'application/json',
        //     },
        //     body: JSON.stringify({
        //         push_subscription: subscription.toJSON()
        //     })
        // });

        // if (response.ok) {
        //     pushEnabled = true;
        //     updatePushUI();
        //     updatePushHint();
        //     return true;
        // } else {
        //     const errorText = await response.text();
        //     throw new Error('Failed to save subscription: ' + errorText);
        //     updatePushUI();
        // }
    }

    async unsubscribe() {
        await this.OneSignal.User.PushSubscription.optOut();
    }

    async refreshUI() {
        const optedIn = await this.OneSignal.User.PushSubscription.optedIn;
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