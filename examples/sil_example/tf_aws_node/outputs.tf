output "public_ip" {
  value = aws_instance.node.public_ip
}

output "instance_id" {
  value = aws_instance.node.id
}
