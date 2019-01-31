import Component from '@ember/component';
import template from './template';
import { layout, attribute, classNames } from '@ember-decorators/component';
import { action, computed, observes } from '@ember-decorators/object';

@layout(template)
@classNames('doc-item-value')
export default class DocItemValueComponent extends Component {
  @attribute
  @computed('meta.action')
  get contenteditable() {
    return this.meta && this.meta.action == 'edit'
  };

  @computed('value')
  get jsonValue() {
    return JSON.parse(this.value);
  }

  @computed('meta.choices')
  get choices() {
    if (!this.meta.choices) { return []; }
    return this.meta.choices;
  }

  didInsertElement() {
    super.didInsertElement(...arguments);
  }

  @action onButtonClick(evt) {
    evt.stopPropagation();
    this.onChange();
  }

  @action onLockClick(evt) {
    evt.stopPropagation();
    this.onLock();
  }

  didReceiveAttrs() {
    this.set('textValue', this.value);
  }

  @observes('value')
  updateTextValue() {
    this.set('textValue', this.value);
  }


  @action updateDateValue(dates, val) {
    this.onChange(val)
  }

  @action updateFromText() {
    if (this.textValue == this.value) { return; }
    this.onChange(this.textValue)
  }

  @action updateValue(evt) {
    evt.stopPropagation();
    this.set('focused', false);
    let val = evt.target.value;
    if (this.value == val) { return; }
    this.onChange(evt.target.value);
  }
}
