from apimas.errors import ValidationError
from panoramix_service import models
from django.db.models import Q, F


def get_endpoint_for_update(endpoint_id):
    try:
        return models.Endpoint.objects.select_for_update().get(
            endpoint_id=endpoint_id)
    except models.Endpoint.DoesNotExist:
        raise ValidationError()


def set_cycle(backend_input, instance, context):
    assert instance is None
    kwargs = context['request/meta/kwargs']
    endpoint_id = kwargs['id0']
    endpoint = get_endpoint_for_update(endpoint_id)
    if not endpoint.public:
        raise ValidationError('Cannot post to a private endpoint')

    if endpoint.current_cycle is None:
        raise ValidationError('No open cycle')
    backend_input['cycle_id'] = endpoint.current_cycle_id


def new_cycle(backend_input, endpoint_id, context):
    endpoint = get_endpoint_for_update(endpoint_id)
    current_cycle = endpoint.current_cycle
    new_cycle = (current_cycle.cycle if current_cycle else 0) + 1
    cycle = models.Cycle.objects.create(
        cycle=new_cycle,
        endpoint_id=endpoint_id,
        **backend_input)
    endpoint.current_cycle = cycle
    endpoint.save()
    return cycle


def update_non_current(context):
    return ~Q(pk=F('endpoint__current_cycle_id'))


def bulk_upload(backend_input, cycle, context):
    messages_input = backend_input['cycle_messages']
    endpoint = cycle.endpoint
    if endpoint.current_cycle != cycle:
        raise ValidationError("Cycle is not current")
    messages = []
    for message_input in messages_input:
        messages.append(
            models.Message(endpoint=endpoint,
                           cycle=cycle,
                           **message_input))

    models.Message.objects.bulk_create(messages)


def set_message_state(backend_input, cycle, context):
    objects = cycle.cycle_messages
    action_input = backend_input['cycle_messages']
    if len(action_input) == 1 and action_input[0]['id'] == -1:
        state = action_input[0]['state']
    else:
        message_ids = [msg['id'] for msg in action_input]
        states = set(msg['state'] for msg in action_input)
        if len(states) != 1:
            raise ValidationError("Must set the same state")
        state = states.pop()
        objects = objects.filter(id__in=message_ids)

    objects.update(state=state)


def purge(backend_input, cycle, context):
    assert not backend_input
    endpoint = cycle.endpoint
    if endpoint.current_cycle == cycle:
        raise ValidationError('Cannot purge the current cycle')
    cycle.cycle_messages.all().delete()
