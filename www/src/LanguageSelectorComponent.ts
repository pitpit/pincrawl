class LanguageSelectorComponent {

    select: HTMLSelectElement | null = null;
    initialLanguage: string | null = null;

    constructor(selectId: string) {
        this.select = document.getElementById(selectId) as HTMLSelectElement | null;
    }

    public async mount() {
        if (this.select) {
            this.initialLanguage = this.select.value;
            this.select.addEventListener('change', async () => {
                if (this.select) {
                    this.select.disabled = true;

                    try {
                        const response = await fetch('/api/my-account', {
                            method: 'PUT',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                language: this.select.value
                            })
                        });

                        if (!response.ok) {
                            throw new Error('Failed to save language preference');
                        }

                        this.initialLanguage = this.select.value;

                    } catch (error) {
                        this.select.value = this.initialLanguage || ''; // Revert
                    } finally {
                        this.select.disabled = false;
                    }
                }
            });
        }
    }
}

export default LanguageSelectorComponent;