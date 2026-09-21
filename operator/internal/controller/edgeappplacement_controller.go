/*
Copyright 2025.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package controller

import (
	"context"
	"encoding/json"
	"time"

	ckafka "github.com/confluentinc/confluent-kafka-go/kafka"

	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	logf "sigs.k8s.io/controller-runtime/pkg/log"

	edgev1 "github.com/mdalgitsis/ran-aware-edge-autoscaling/operator/api/v1"
)

// EdgeAppPlacementReconciler reconciles a EdgeAppPlacement object
type EdgeAppPlacementReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

var log = logf.Log.WithName("controller_edgeappplacement")

// +kubebuilder:rbac:groups=edge.ranaware.dev,resources=edgeappplacements,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=edge.ranaware.dev,resources=edgeappplacements/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=edge.ranaware.dev,resources=edgeappplacements/finalizers,verbs=update

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
// TODO(user): Modify the Reconcile function to compare the state specified by
// the EdgeAppPlacement object against the actual cluster state, and then
// perform operations to make the cluster state reflect the state specified by
// the user.
//
// For more details, check Reconcile and its Result here:
// - https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.21.0/pkg/reconcile
func (r *EdgeAppPlacementReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.WithValues("edgeappplacement", req.NamespacedName)

	var placement edgev1.EdgeAppPlacement
	if err := r.Get(ctx, req.NamespacedName, &placement); err != nil {
		logger.Error(err, "unable to fetch EdgeAppPlacement")
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	// 1. Check for spec/status mismatch
	if placement.Spec.EdgeNodeID != placement.Status.LastNotifiedEdgeNodeID {
		// New migration detected — reset KafkaNotificationSent
		if placement.Status.KafkaNotificationSent {
			placement.Status.KafkaNotificationSent = false
			if err := r.Status().Update(ctx, &placement); err != nil {
				logger.Error(err, "failed to reset KafkaNotificationSent flag")
				return ctrl.Result{}, err
			}
			// Requeue to trigger actual Kafka logic in next cycle
			return ctrl.Result{Requeue: true}, nil
		}
	}

	// 2. If edge node matches, check if notification already sent
	if placement.Spec.EdgeNodeID == placement.Status.LastNotifiedEdgeNodeID {
		if placement.Status.KafkaNotificationSent {
			// Already notified, skip everything — avoid redundant log
			return ctrl.Result{}, nil
		}

		// Log skipped migration
		logger.Info("No migration detected, skipping Kafka notification",
			"EdgeNodeID", placement.Spec.EdgeNodeID,
			"appID", placement.Name)
		return ctrl.Result{}, nil
	}

	// 3. Send Kafka message
	payload := map[string]interface{}{
		"event":        placement.Spec.Kafka.Message.EventType,
		"new_location": placement.Spec.EdgeNodeID,
		"timestamp":    time.Now().Unix(),
	}

	messageBytes, err := jsonMarshal(payload)
	if err != nil {
		logger.Error(err, "failed to marshal Kafka payload")
		return ctrl.Result{}, err
	}

	producer, err := ckafka.NewProducer(&ckafka.ConfigMap{
		"bootstrap.servers": placement.Spec.Kafka.Broker,
	})
	if err != nil {
		logger.Error(err, "failed to create Kafka producer")
		return ctrl.Result{}, err
	}
	defer producer.Close()

	deliveryChan := make(chan ckafka.Event)
	defer close(deliveryChan)

	err = producer.Produce(&ckafka.Message{
		TopicPartition: ckafka.TopicPartition{
			Topic:     &placement.Spec.Kafka.Topic,
			Partition: ckafka.PartitionAny,
		},
		Value: messageBytes,
	}, deliveryChan)
	if err != nil {
		logger.Error(err, "failed to produce Kafka message")
		return ctrl.Result{}, err
	}

	e := <-deliveryChan
	msg := e.(*ckafka.Message)
	if msg.TopicPartition.Error != nil {
		logger.Error(msg.TopicPartition.Error, "Kafka message delivery failed")
		return ctrl.Result{}, msg.TopicPartition.Error
	}

	logger.Info("Kafka message delivered successfully",
		"topic", placement.Spec.Kafka.Topic,
		"edgeNodeID", placement.Spec.EdgeNodeID,
		"appID", placement.Name)

	// 4. Update status
	placement.Status.LastNotifiedEdgeNodeID = placement.Spec.EdgeNodeID
	placement.Status.LastNotificationTime = time.Now().Format(time.RFC3339)
	placement.Status.KafkaNotificationSent = true
	if err := r.Status().Update(ctx, &placement); err != nil {
		logger.Error(err, "failed to update EdgeAppPlacement status")
		return ctrl.Result{}, err
	}

	return ctrl.Result{}, nil
}

func (r *EdgeAppPlacementReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&edgev1.EdgeAppPlacement{}).
		Named("edgeappplacement").
		Complete(r)
}

// Helper: Marshal JSON with consistent format
func jsonMarshal(v interface{}) ([]byte, error) {
	return json.MarshalIndent(v, "", "  ")
}
