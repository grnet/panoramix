import Route from '@ember/routing/route';

export default Route.extend({
  redirect(transition) {
    this.transitionTo('election', 'trustee1');
  }
});
