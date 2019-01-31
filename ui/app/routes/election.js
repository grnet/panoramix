import Route from '@ember/routing/route';
import { service } from '@ember-decorators/service';
import { set } from '@ember/object';
import { hash } from 'rsvp';

export default class ElectionRoute extends Route {
  @service api;

  init() {
    super.init(...arguments);
    this.set('queryParams', { manual: {} });
  }

  model({user}) {
    this.users = user.split(',');
    this.stages = {};
    this.negId = null;
    let promises = {};

    this.users.forEach((user) => {
      promises[user] = this.api.initStages(user, this.negId);
    });

    return hash(promises).then((models) => {
      let sorted = {};
      this.users.forEach((user) => {
        sorted[user] = models[user];
      });
      return sorted;
    });
  }

  setupController(controller, model) {
    super.setupController(...arguments);
    set(controller, 'users', this.users);
    set(controller, 'negId', this.negId);
    let key = Object.keys(model)[0]
    set(controller, 'appSubtitle', model[key].stage_A.global_negotiation);

    let runningPaths = [];
    controller.updateRunningPaths(runningPaths);
    window.$E = controller;
    window.model = model;
  }

  activate() {
    this.controllerFor('election').get('refreshModels').perform();
  }

  deactivate() {
    this.controllerFor('election').get('refreshModels').stop();
  }
}
