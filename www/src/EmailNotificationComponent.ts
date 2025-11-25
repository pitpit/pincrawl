import States from './States';

class EmailNotificationComponent {

    emailButton: HTMLButtonElement | null;
    emailButtonStates: States;

    constructor(emailButtonId: string) {
        this.emailButton = document.getElementById(emailButtonId) as HTMLButtonElement | null;
        this.emailButtonStates = new States(this.emailButton);
    }

    public async mount() {
        if (this.emailButton) {
            this.emailButton.addEventListener('click', async () => {
                if (!this.emailButton) {
                    return;
                }

                var emailEnabled = this.emailButtonStates.getCurrent() === 'enabled';
                this.emailButtonStates.change('loading');

                try {
                    emailEnabled = !emailEnabled;
                    await this.pushEmailNotification(emailEnabled);
                } catch (error) {
                    emailEnabled = !emailEnabled;
                } finally {
                    this.emailButtonStates.change(emailEnabled ? 'enabled' : 'disabled');
                }
            });
        }
    }

    private async pushEmailNotification(enabled: boolean): Promise<void> {
        const response = await fetch('/api/my-account', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email_notifications: enabled
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error('Failed to update email preference: ' + errorText);
        }
    }
}

export default EmailNotificationComponent;