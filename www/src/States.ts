class States {

    element: HTMLElement | null = null

    constructor(element: HTMLElement|null) {
        this.element = element;

        // Initialize to current state of data-state existing on element
        const currentState = this.getCurrent();
        if (currentState) {
            this.change(currentState);
        }
    }

    getCurrent(): string {
        return this.element ? this.element.getAttribute('data-state') || '' : '';
    }

    change(state: string) {
        if (!this.element) {
            return;
        }

        this.element.setAttribute('data-state', state);

        // Load all data-state-* attributes
        const stateAttributes: { [key: string]: string } = {};
        for (let i = 0; i < this.element.attributes.length; i++) {
            const attr = this.element.attributes[i];
            if (attr.name.startsWith('data-state')) {
                stateAttributes[attr.name] = attr.value;
            }
        }

        this.element.textContent = stateAttributes['data-state[' + state + '].text-content'] || this.element.textContent || '';
        this.element.className = stateAttributes['data-state[' + state + '].classname'] || '';
        if (this.element instanceof HTMLButtonElement) {
            this.element.disabled = (stateAttributes['data-state[' + state + '].disabled'] || 'false').toLowerCase() === 'true';
        }
    }
}

export default States;