import Component from '@ember/component';
import { argument } from '@ember-decorators/argument';
import { computed } from '@ember-decorators/object';
import { classNames, className } from '@ember-decorators/component';
import { capitalize } from '@ember/string';

@classNames('stage')
export default class StageViewComponent extends Component {
  @argument meta;
  @argument stage;
  @argument expanded;
  @argument expandedPaths;
  @argument actionDisabled;
  @argument('action') docAction;
  @argument('action') onValueChange;
  @argument('action') onKeyLock;
  @argument('action') expandPath;
  @argument('action') collapsePath;
  @argument('action') showStatus;

  actionableLabels = ['FINISH', 'PROPOSE', 'TRANSITION', 'ENHANCE', 'CONSENT', 'CONFLICT']
  actionLabelMap = {
    'ENHANCE': 'CONSENT & PROPOSE',
    'NO_TRANSITION': 'PROPOSE',
    'AUTOCLOSE': 'WAIT'
  }

  @computed('meta.state_label')
  get actionCls() {
    let state_label = this.meta.state_label;
    if (!state_label) { return; }
    return 'to-state-' + state_label.toLowerCase();
  }

  @computed('meta.state_label')
  get actionLabel() {
    let state_label = this.meta.state_label;
    let label = this.actionLabelMap[(state_label || '').toUpperCase()] || state_label && state_label.split('_').join(' ') || 'WAIT';
    return capitalize(label);
  }

  @computed('meta.state_label')
  get canAction() {
    let label = this.meta.state_label;
    return this.actionableLabels.includes(label && label.toUpperCase());
  }
}
